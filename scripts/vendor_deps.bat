@echo off
setlocal

cd /d "%~dp0\.."

if not exist vendor\site-packages mkdir vendor\site-packages

python -m pip install --upgrade pip
python -m pip install -r requirements.txt --target vendor\site-packages --no-compile

rem setuptools is install-time only; remove it from the runtime bundle
if exist vendor\site-packages\setuptools rmdir /s /q vendor\site-packages\setuptools
if exist vendor\site-packages\setuptools-*.dist-info rmdir /s /q vendor\site-packages\setuptools-*.dist-info
if exist vendor\site-packages\_distutils_hack rmdir /s /q vendor\site-packages\_distutils_hack
if exist vendor\site-packages\distutils-precedence.pth del /q vendor\site-packages\distutils-precedence.pth
if exist vendor\site-packages\bin rmdir /s /q vendor\site-packages\bin

echo.
echo Vendored packages installed to vendor\site-packages
echo Commit the updated vendor\site-packages folder to git.
