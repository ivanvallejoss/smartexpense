"""
Pipeline de mensajería entrante y saliente.

El nombre 'bot' es histórico: nació como app específica de Telegram.
Desde el refactor multi-canal, todo lo que hay acá es agnóstico al canal
salvo la configuración del webhook en views.py y urls.py.

No se renombró a 'messaging' porque el comando de arranque del worker
(`arq apps.bot.worker.WorkerSettings`) está en docker-compose.yml y en la
config de deploy: renombrar exige coordinar el deploy sin ganancia funcional.
Vale la pena cuando entre el segundo canal.
"""
