@echo off
setlocal

rem ============================================================
rem spring-ai-demo launcher
rem 1) pin JDK / Maven  2) load API key from week3 keys.env
rem 3) start Spring Boot
rem Keep this file ASCII-only: cmd.exe + UTF-8 is fragile.
rem ============================================================

set "JAVA_HOME=D:\Java\jdk-21.0.13.9-hotspot"
set "MAVEN_HOME=D:\Tools\apache-maven-3.9.16"
set "PATH=%JAVA_HOME%\bin;%MAVEN_HOME%\bin;%PATH%"
set "KEYS=%~dp0..\week3-ai-basics\python-lab\keys.env"

if not exist "%KEYS%" goto nokeys

rem parse KEY=VALUE lines, skip comment lines starting with #
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%KEYS%") do (
    if not "%%a"=="" set "%%a=%%b"
)

if "%DASHSCOPE_API_KEY%"=="" goto nokey

echo [OK] key loaded
echo [OK] JDK = %JAVA_HOME%
echo [OK] starting... open http://localhost:8080/ when you see "Started AiApplication"
call mvn -B spring-boot:run
goto end

:nokeys
echo [ERROR] keys.env not found: %KEYS%
echo         copy keys.env.example to keys.env and fill in your key first.
pause
exit /b 1

:nokey
echo [ERROR] DASHSCOPE_API_KEY is missing in keys.env
pause
exit /b 1

:end
endlocal
