"""
Entry-point WSGI para gunicorn em producao.
Uso: gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -b 127.0.0.1:5000 backend.wsgi:app
"""

from backend.app import app, socketio  # noqa: F401

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
