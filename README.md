# pregit

Markdown compatible Wiki system for Git backend.

## Usage
- Use for knowledge base.
- Use for take meeting minutes.
- Use for operating procedure manual.
- Use for ownself. or use for multi users and teams.
- Those who want to use Markdown preview even on-premises environment or local environment where cloud environment can not be used.


## Features
- Support Git repository. and `git clone`, `git push`.
- Support text files too.
- Support markdown format.
    - Like GFM and CommonMark. and more. ref:[beckorz/previm](https://github.com/beckorz/previm) features.
- Works cross-platform.(Win/Linux/Mac).
- Having built-in web server, and reverse proxy support.
    - SSL support(Apache, nginx etc).
- PDF file download feature. (by [wkhtmltopdf](https://wkhtmltopdf.org/))
- Raw file download feature.


## Requirement
- Python 3 (Python 3.5 later)
- Git client (Optional)
- wkhtmltopdf (Optional)


### Install python dependencies

Python requirements:

- chardet

    ```sh
    pip install chardet
    ```

- Flask

    ```sh
    pip install flask
    ```

or

```sh
pip install -r requirements.txt
```


## Installation 
1. Install Git client.(Optional)
2. Install python 3. (3.5 later)
3. Install python dependencies.
4. Edit the `config.ini`. (Ref: `config.example.ini`)
    - And create sample directory.(For Windows)
        - Execute `initial_sample_repo.bat`
5. Start server.

    ```sh
    python app.py
    ```

6. Open `http://localhost:5000/` in your browser.

If you want to modify the file, please fix it by `git clone`,` git push`.


## NOTE
- Need for bare repository in GIT.
- To output PDF, [wkhtmltopdf](https://wkhtmltopdf.org) is necessary.


## Support browser
IE11, Edge, Firefox, Chrome, Safari


## Customizing
- Style
    - /static/css/\*


## TODO
- [ ] auth.
- [ ] Support mathjax.
- [ ] YAML front matter.
- [ ] Switch tasklist.
- [ ] Notification.
- [ ] Show activity page.
- [ ] Text avater / Gravatar
- [ ] Sample page.


## Thanks
- [Gollum](https://github.com/gollum/gollum)
- [previm](http://github.com/previm/previm/)
- [gitprep](http://gitprep.yukikimoto.com/)
- [wkhtmltopdf](https://wkhtmltopdf.org/)
- [Octicons](https://octicons.github.com/)
- [Honoka](http://honokak.osaka/)


## License
[MIT License](LICENSE)

