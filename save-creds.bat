echo Guardando credenciales...
echo.
echo 1. Cuando pida usuario para CORE0: HOMYS
echo 2. Cuando pida contrasena: [password de HOMYS en CORE0]
cmdkey /generic:TERMSRV/192.168.1.17
echo.
echo 3. Quando pida usuario para este PC: Usuario  
echo 4. Cuando pida contrasena: [tu password de Windows]
cmdkey /generic:TERMSRV/192.168.1.18
echo.
cmdkey /list
pause