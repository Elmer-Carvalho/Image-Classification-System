@echo off
echo ========================================
echo Sistema de Classificação de Imagens
echo ========================================
echo.

echo Iniciando serviços com Docker...
docker-compose up -d

echo.
echo Aguardando serviços iniciarem...
timeout /t 10 /nobreak > nul

echo.
echo Verificando status dos serviços...
docker-compose ps

echo.
echo ========================================
echo Sistema iniciado com sucesso!
echo ========================================
echo.
echo Acesse:
echo - API: http://localhost:8000
echo - Documentação: http://localhost:8000/docs
echo - Health Check: http://localhost:8000/health
echo.
echo Para ver logs: docker-compose logs -f
echo Para parar: docker-compose down
echo.
pause 