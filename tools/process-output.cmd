@echo off
setlocal

cd /d "%~dp0\.."

if not exist input mkdir input
if not exist output mkdir output
if not exist temp mkdir temp

docker build -t ocap-renderterrain:latest ocap-renderterrain
if errorlevel 1 exit /b %errorlevel%

docker run --rm --name ocap-renderterrain ^
  --mount type=bind,src="%CD%\input",target=/app/input ^
  --mount type=bind,src="%CD%\output",target=/app/output ^
  --mount type=bind,src="%CD%\temp",target=/app/temp ^
  --memory=36g ^
  ocap-renderterrain:latest

exit /b %errorlevel%
