@echo off
setlocal EnableExtensions

set "MOD_ROOT=%~dp0"
if "%MOD_ROOT:~-1%"=="\" set "MOD_ROOT=%MOD_ROOT:~0,-1%"

set "DOCKER_CONTEXT=%MOD_ROOT%\ocap_renderterrain"
if not exist "%DOCKER_CONTEXT%\Dockerfile" (
    echo Docker context not found: "%DOCKER_CONTEXT%"
    exit /b 1
)

set "ARMA_ROOT=%CD%"
if exist "%ARMA_ROOT%\ocap_exporter\" goto :haveArmaRoot

if exist "%MOD_ROOT%\..\ocap_exporter\" (
    pushd "%MOD_ROOT%\.." >nul
    set "ARMA_ROOT=%CD%"
    popd >nul
)

:haveArmaRoot
if not exist "%ARMA_ROOT%\ocap_exporter\" (
    echo Could not find exported source data at "%ARMA_ROOT%\ocap_exporter".
    echo Run this from your Arma 3 root, or place @ocap_renderterrain inside the Arma 3 root.
    exit /b 1
)

set "INPUT_DIR=%ARMA_ROOT%\ocap_exporter"
set "OUTPUT_DIR=%ARMA_ROOT%\ocap_renderterrain_output"
set "TEMP_DIR=%ARMA_ROOT%\ocap_renderterrain_temp"
set "WORLDS=%~1"
if "%OCAP_RENDER_DOCKER_MEMORY%"=="" set "OCAP_RENDER_DOCKER_MEMORY=48g"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

echo Building Docker image from "%DOCKER_CONTEXT%"...
docker build -t ocap-renderterrain:latest "%DOCKER_CONTEXT%"
if errorlevel 1 exit /b %errorlevel%

docker rm -f ocap-renderterrain-manual >nul 2>nul

echo Processing source data from "%INPUT_DIR%"...
if "%WORLDS%"=="" (
    docker run --rm --name ocap-renderterrain-manual ^
      --mount type=bind,src="%INPUT_DIR%",target=/app/input ^
      --mount type=bind,src="%OUTPUT_DIR%",target=/app/output ^
      --mount type=bind,src="%TEMP_DIR%",target=/app/temp ^
      --env OCAP_RENDER_MAX_SIZE=32768 ^
      --memory=%OCAP_RENDER_DOCKER_MEMORY% ^
      ocap-renderterrain:latest
) else (
    docker run --rm --name ocap-renderterrain-manual ^
      --mount type=bind,src="%INPUT_DIR%",target=/app/input ^
      --mount type=bind,src="%OUTPUT_DIR%",target=/app/output ^
      --mount type=bind,src="%TEMP_DIR%",target=/app/temp ^
      --env "OCAP_RENDER_WORLDS=%WORLDS%" ^
      --env OCAP_RENDER_MAX_SIZE=32768 ^
      --memory=%OCAP_RENDER_DOCKER_MEMORY% ^
      ocap-renderterrain:latest
)

exit /b %errorlevel%
