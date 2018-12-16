SET CUR_DIR=%~dp0
SET REPO=%CUR_DIR%repo
SET PREGIT_RAW_DIR=%CUR_DIR%raw\sample
SET WORK_TEMP_DIR=%CUR_DIR%tmp
SET WORK_TREE_DIR=%WORK_TEMP_DIR%\work

rmdir /s /q %REPO%
rmdir /s /q %WORK_TEMP_DIR%

mkdir %REPO%
git init -q --bare %REPO%

REM Workdir
mkdir %WORK_TREE_DIR%
cd %WORK_TREE_DIR%
git init -q
xcopy /s %PREGIT_RAW_DIR%\* sample\
git add .
git config user.name "Anonymous"
git config user.email ""
git commit -q -m "first commit"
git push -q "%REPO%" master
