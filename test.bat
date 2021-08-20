call .\build.bat

docker volume create midog2021-output

docker run --rm^
 --memory=4g^
 -v %~dp0\test\:/input/^
 -v midog2021-output:/output/^
 midog2021

docker run --rm^
 -v midog2021-output:/output/^
 python:3.7-slim cat /output/metrics.json | python -m json.tool

docker volume rm midog2021-output
