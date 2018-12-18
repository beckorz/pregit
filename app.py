import os
import os.path
import glob
import re
import sys
import gzip
import io
import logging
import logging.config
import urllib.parse
import configparser
import mimetypes
import chardet
from flask import Flask, make_response, request, abort, render_template, send_file, send_from_directory
import subprocess
import time
from datetime import datetime
import locale
from operator import itemgetter

locale.setlocale(locale.LC_ALL, '')

# Logging config
app = Flask(__name__)
app.url_map.strict_slashes = False
logging.config.fileConfig('logging.ini')    # by logging config file.
logger = logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)


class NoLoggingFilter(logging.Filter):
    def filter(self, record):
        log_message = record.getMessage()
        return 'static' not in log_message


logging.getLogger('werkzeug').addFilter(NoLoggingFilter())

# Load general config.
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')
conf = config['General']

DIRECTORY_MODE = conf.getint('directory.mode', 1)  # 0: Normal dir, 1: Single git repo, 2: Multi git repos
BASE_DIR = conf.get('base.dir', '.')
IS_DEBUG_MODE = conf.getboolean('is.debug.mode', False)
HOST = conf.get('host', None)
PORT = conf.get('port', None)
THREADED = conf.getboolean('threaded', False)
DATE_FORMAT = conf.get('date.format', '%Y/%m/%d (%a) %H:%M:%S', raw=True)
ENABLE_REALTIME_PREVIEW = conf.getboolean('enable.realtime.preview', True)
DEFAULT_ENCODING = conf.get('detault.encoding', 'utf-8')
PDF_WRITER_BIN = conf.get('pdf.writer.bin', 'wkhtmltopdf')
PDF_WRITER_ARGS = conf.get('pdf.writer.args', '')


def _age_ago(unit, age):
    return "{} {}{} ago".format(age, unit, 's' if age > 1 else '')


def get_age_string(age):
    if age >= 60 * 60 * 24 * 365:
        age_str = _age_ago('year', int(age / 60 / 60 / 24 / 365))  # year
    elif (age >= 60 * 60 * 24 * (365 / 12)):
        age_str = _age_ago('month', int(age / 60 / 60 / 24 / (365 / 12)))  # month
    elif (age >= 60 * 60 * 24 * 7):
        age_str = _age_ago('week', int(age / 60 / 60 / 24 / 7))  # week
    elif(age >= 60 * 60 * 24):
        age_str = _age_ago('day', int(age / 60 / 60 / 24))  # day
    elif (age >= 60 * 60):
        age_str = _age_ago('hour', int(age / 60 / 60))  # hour
    elif (age >= 60):
        age_str = _age_ago('min', int(age / 60))  # min
    elif (age >= 1):
        age_str = _age_ago('sec', int(age))  # sec
    else:
        age_str = 'right now'
    age_str = re.sub('^1 ', 'a ', age_str)
    age_str = re.sub('^a hour', 'an hour', age_str)
    return age_str


def get_file_timestamp(path):
    if DIRECTORY_MODE == 0:
        path = path.replace(BASE_DIR + os.path.sep, '')  # remove
        path = os.path.join(BASE_DIR, path)              # add
        return os.path.getmtime(path)
    else:
        # TODO: FileTimestamp
        return 0


def make_breadcrumbs(path):
    """Make bread crumbs.
    The top is automatically generated automatically.
    """
    DELIMITER = '/'
    breadcrumbs = []
    breadcrumbs.append({'title': 'Top', 'path': '', 'current': False})
    splitPath = path.split(DELIMITER)
    for i, crumb in enumerate(splitPath):
        breadcrumbs.append({'title': crumb,
                            'path': DELIMITER.join(splitPath[0:i + 1]),
                            'current': len(splitPath) == i + 1})
    return breadcrumbs


def get_repository_path(projectName):
    if DIRECTORY_MODE == 0:
        # Normal
        return BASE_DIR
    elif DIRECTORY_MODE == 1:
        # Single git repository
        return BASE_DIR
    elif DIRECTORY_MODE == 2:
        # TODO: Multi git repository
        return os.path.join(BASE_DIR, projectName)
    pass


def execute_cmd(rep, cmd):
    p = subprocess.Popen(cmd, cwd=rep, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = p.stdout.read()
    p.stdout.flush()
    p.wait()
    out, err = p.communicate()
    return data


def path_to_hash(rep, rev, filePath, typeName):
    cmd = ['git', 'ls-tree', rev, '--', filePath]
    data = execute_cmd(rep, cmd)
    # 100644 blob 17d2df581f6b153fc030167743db637d97104ff2\t<file>\n
    m = re.match('^[0-9]+ (.+) ([0-9a-fA-F]{40})', str(data.decode()))
    if m:
        if m.group(1) == typeName:
            return m.group(2)


def get_blob_file(rep, rev, filePath):
    if DIRECTORY_MODE == 0:
        path = os.path.join(rep, rev, filePath)
        path = path.replace('\\', '/')
        if '..' in path:
            raise ValueError('Directory traversal error: ' + path)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return f.read()
        else:
            raise FileNotFoundError('No such file or directory.' + path)
    else:
        hash = path_to_hash(rep, rev, filePath, 'blob')
        cmd = ['git', 'cat-file', 'blob', hash]
        data = execute_cmd(rep, cmd)
        return data


def get_trees(rep, rev, dir):
    if DIRECTORY_MODE == 0:
        targetPath = os.path.join(BASE_DIR, dir)
        files = glob.glob(targetPath + '/*')
        items = []
        for file in files:
            item = {}
            timestamp = get_file_timestamp(file)
            date = datetime.fromtimestamp(timestamp).strftime(DATE_FORMAT)
            age_ago = get_age_string(time.time() - timestamp)
            item['timestamp'] = timestamp
            item['datetime'] = date
            item['age'] = age_ago
            if os.path.isdir(file):
                item['type'] = 'dir'
                item['path'] = 'pages/' + file.replace(BASE_DIR + os.path.sep, '')
                pass
            else:
                item['type'] = 'file'
                item['path'] = '' + file.replace(BASE_DIR + os.path.sep, '')
            item['name'] = os.path.basename(file)
            items.append(item)
        return items
    else:
        if dir == '':
            cmd = ['git', 'ls-tree', '-z', rev]
        else:
            cmd = ['git', 'ls-tree', '-z', rev + ':' + dir]
        data = execute_cmd(rep, cmd)
        data = data.decode().split('\0')
        # Parse tree
        items = []
        for line in data:
            m = re.match('^([0-9]+) (.+) ([0-9a-fA-F]{40})\t(.+)$', line)
            if m:
                item = {}
                # TODO: Get time stamp
                item['timestamp'] = ''
                item['datetime'] = ''
                item['age'] = ''
                if m.group(2) == 'tree':
                    item['type'] = 'dir'
                    item['path'] = 'pages/' + os.path.join(dir, m.group(4))
                else:
                    item['type'] = 'file'
                    item['path'] = os.path.join(dir, m.group(4))
                item['name'] = m.group(4)
                items.append(item)
        return items


@app.route('/', methods=('GET',))
def index():
    data = {}
    data['directory_mode'] = DIRECTORY_MODE
    data['clone_url'] = request.url
    data['base_dir'] = BASE_DIR
    return render_template('index.html', data=data)


@app.route('/favicon.ico', methods=('GET',))
def send_favicon():
    "Send static file favicon.ico"
    return send_from_directory('static', 'favicon.ico')


@app.route('/pages/<path:dir>', methods=('GET',))
@app.route('/pages', defaults={'dir': ''}, methods=('GET',))
def pages(dir=''):
    try:
        repoPath = get_repository_path('')
        branch = 'master'
        data = {}
        data['breadcrumbs'] = make_breadcrumbs(dir)
        data['branch'] = branch
        if dir == '':
            data['breadcrumb'] = 'Home'
            data['pagelist'] = 'pages'
        else:
            data['breadcrumb'] = 'Home'
            data['pagelist'] = 'pages/' + dir
        # data['pages'] = sorted(get_trees(repoPath, branch, dir), key=lambda x: x['type'])
        pageList = get_trees(repoPath, branch, dir)
        sortedList = sorted(pageList, key=itemgetter('type', 'name'))
        data['pages'] = sortedList
        return render_template('pages.html', data=data)
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/js/previm-function.js', methods=('GET',))
def previm_function():
    # Previm dynamic
    try:
        path = request.args.get('path')
        if DIRECTORY_MODE == 0:
            rev = ''
        else:
            rev = request.args.get('rev', 'master')
        data = {}
        data['is_show_header'] = '1'                        # TODO:
        data['file_name'] = path
        data['file_type'] = 'markdown'                      # TODO:
        repoPath = get_repository_path('')
        blob = get_blob_file(repoPath, rev, path)
        # Detect charset
        charset = chardet.detect(blob)
        try:
            content = blob.decode(charset['encoding'])
        except UnicodeDecodeError:
            app.logger.debug('Detect file encode error: {}. and using default encoding.({})'.format(charset['encoding'], DEFAULT_ENCODING))
            content = blob.decode(DEFAULT_ENCODING)
        # Escape string
        content = content.replace("\\", "\\\\")     # \
        content = content.replace("\"", "\\\"")     # "
        content = content.replace("\r\n", "\\n")    # CRLF
        content = content.replace("\r", "\\n")      # CR
        content = content.replace("\n", "\\n")      # LF
        timestamp = get_file_timestamp(path)
        date = datetime.fromtimestamp(timestamp).strftime(DATE_FORMAT)
        age_ago = get_age_string(time.time() - timestamp)
        data['last_modified'] = date
        data['age_ago'] = age_ago
        data['content'] = content
        res = make_response(render_template('previm-function.js', data=data))
        res.headers['Content-type'] = 'text/javascript'
        return res
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/js/previm.js', methods=('GET',))
def previmjs():
    # Previm main script
    try:
        path = request.args.get('path')
        data = {}
        data['path'] = urllib.parse.quote(path)
        data['enable_realtime_preview_default'] = str(ENABLE_REALTIME_PREVIEW).lower()
        res = make_response(render_template('previm.js', data=data))
        res.headers['Content-type'] = 'text/javascript'
        return res
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/<path:filePath>', methods=('GET',))
def req(filePath):
    """Request
    """
    try:
        repoPath = get_repository_path('')
        if DIRECTORY_MODE == 0:
            rev = ''
        else:
            rev = 'master'
        blob = get_blob_file(repoPath, rev, filePath)
        fileType = mimetypes.guess_type(filePath)
        if fileType[0] is None or 'text/plain' == fileType[0]:
            # (None, None) also markdown and normal text
            app.logger.debug('None type')
            data = {}
            data['title'] = 'Preview'
            data['path'] = urllib.parse.quote(filePath)
            return render_template('preview.html', data=data)
            pass
        else:
            res = make_response(blob)
            res.headers['Content-Type'] = fileType[0]
            return res
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/blob/<path:filePath>', defaults={'rev': '', 'project_name': ''}, methods=('GET',))
@app.route('/<string:project_name>/blob/<string:rev>/<path:filePath>', methods=('GET',))
def raw(project_name, rev, filePath):
    try:
        repoPath = get_repository_path(project_name)
        if DIRECTORY_MODE == 0:
            rev = ''
            filePath = os.path.join(rev, filePath)
        blob = get_blob_file(repoPath, rev, filePath)
        return send_file(io.BytesIO(blob),
                         attachment_filename=os.path.basename(filePath),
                         as_attachment=True)
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/pdf/<path:filePath>', defaults={'rev': '', 'project_name': ''}, methods=('GET',))
@app.route('/<string:project_name>/pdf/<string:rev>/<path:filePath>', methods=('GET',))
def pdf(project_name, rev, filePath):
    try:
        if DIRECTORY_MODE == 0:
            rev = ''
            filePath = os.path.join(rev, filePath)
        # TODO: Loopback url and ssl url
        url = 'http://localhost:' + PORT + '/' + filePath
        # Execute wkhtmltopdf
        cmd = (PDF_WRITER_BIN + ' ' + PDF_WRITER_ARGS + ' ' + url + ' -').split(' ')
        data = execute_cmd(None, cmd)
        fileName = os.path.splitext(os.path.basename(filePath))[0] + '.pdf'
        return send_file(io.BytesIO(data),
                         attachment_filename=fileName,
                         as_attachment=True)
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


##############################################################################
# git client api
##############################################################################


@app.route('/info/refs', defaults={'project_name': ''})
@app.route('/<string:project_name>/info/refs')
# @auth.login_required
def info_refs(project_name):
    try:
        if DIRECTORY_MODE != 0:
            service = request.args.get('service')
            if service[:4] != 'git-':
                abort(500)
            repoPath = get_repository_path(project_name)
            p = subprocess.Popen(
                [service, '--stateless-rpc', '--advertise-refs', repoPath],
                stdout=subprocess.PIPE)
            packet = '# service=%s\n' % service
            length = len(packet) + 4
            prefix = "{:04x}".format(length & 0xFFFF)
            data = (prefix + packet + '0000').encode()
            data += p.stdout.read()
            res = make_response(data)
            res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
            res.headers['Pragma'] = 'no-cache'
            res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
            res.headers['Content-Type'] = 'application/x-%s-advertisement' % service
            p.stdout.flush()
            p.wait()
            return res
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/git-receive-pack', defaults={'project_name': ''}, methods=('POST',))
@app.route('/<string:project_name>/git-receive-pack', methods=('POST',))
# @auth.login_required
def git_receive_pack(project_name):
    try:
        if DIRECTORY_MODE != 0:
            repoPath = get_repository_path(project_name)
            p = subprocess.Popen(
                ['git-receive-pack', '--stateless-rpc', repoPath],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            p.stdin.write(request.data)
            p.stdin.flush()
            data_out = p.stdout.read()
            res = make_response(data_out)
            res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
            res.headers['Pragma'] = 'no-cache'
            res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
            res.headers['Content-Type'] = 'application/x-git-receive-pack-result'
            p.wait()
            return res
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


@app.route('/git-upload-pack', defaults={'project_name': ''}, methods=('POST',))
@app.route('/<string:project_name>/git-upload-pack', methods=('POST',))
# @auth.login_required
def git_upload_pack(project_name):
    try:
        if DIRECTORY_MODE != 0:
            repoPath = get_repository_path(project_name)
            if 'Content-Encoding' in request.headers:
                # gzip
                app.logger.debug('Content-Encoding: ' + request.headers['Content-Encoding'])
                reqData = gzip.decompress(request.data)
            else:
                reqData = request.data
            p = subprocess.Popen(
                ['git-upload-pack', '--stateless-rpc', repoPath],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            p.stdin.write(reqData)  # stdin
            p.stdin.flush()
            data = p.stdout.read()  # stdout
            res = make_response(data)
            res.headers['Expires'] = 'Fri, 01 Jan 1980 00:00:00 GMT'
            res.headers['Pragma'] = 'no-cache'
            res.headers['Cache-Control'] = 'no-cache, max-age=0, must-revalidate'
            res.headers['Content-Type'] = 'application/x-git-upload-pack-result'
            p.wait()
            return res
    except Exception:
        app.logger.error(sys.exc_info())
        abort(500)


if __name__ == '__main__':
    app.run(debug=IS_DEBUG_MODE, host=HOST, port=PORT, threaded=THREADED)
