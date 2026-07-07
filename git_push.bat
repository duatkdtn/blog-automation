@echo off
cd /d C:\Users\HOME\Documents\Claude\Projects\블로그자동화
git stash
git pull --rebase
git stash pop
git push
echo.
echo ✅ 푸시 완료!
pause
