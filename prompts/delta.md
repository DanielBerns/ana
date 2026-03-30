# Ana: Autonomous Event-Driven Agent

## Context

Ana is an event-driven, microservice-based AI system built with Hexagonal Architecture. It autonomously scrapes web data, processes RSS feeds, archives artifacts, and features a conversational AI loop, all orchestrated through a RabbitMQ event bus and backed by PostgreSQL.

The system is designed for complete environment isolation. You can run multiple separate "instances" (e.g., `devel`, `testing`, `prod`) on the same machine, each with its own dedicated database, RabbitMQ virtual host, and configuration files.

## Petition

After executing succesfully
    
    make provision INSTANCE=demo 
    make run-configurator INSTANCE=demo

I try to execute
  
    make run-interface INSTANCE=demo
    
and got the error
Starting Interface (Port 8000) for instance: demo...
ANA_INSTANCE=demo uv run uvicorn apps.interface.src.interface.main:app --reload --port 8000
INFO:     Will watch for changes in these directories: ['/home/dberns/Projects/github/DanielBerns/ana']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [130318] using WatchFiles
INFO:     Started server process [130347]
INFO:     Waiting for application startup.
ERROR:    Traceback (most recent call last):
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/abc.py", line 44, in __inner
    return await self.task
           ^^^^^^^^^^^^^^^
asyncio.exceptions.CancelledError

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/starlette/routing.py", line 638, in lifespan
    async with self.lifespan_context(app) as maybe_state:
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/fastapi/routing.py", line 217, in merged_lifespan
    async with nested_context(app) as maybe_nested_state:
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/contextlib.py", line 210, in __aenter__
    return await anext(self.gen)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/faststream/_internal/fastapi/router.py", line 290, in start_broker_lifespan
    await self._start_broker()
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/faststream/_internal/application.py", line 98, in _start_broker
    await b.start()
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/faststream/rabbit/broker/broker.py", line 276, in start
    await self.connect()
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/faststream/_internal/broker/broker.py", line 111, in connect
    self._connection = await self._connect()
                       ^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/faststream/rabbit/broker/broker.py", line 230, in _connect
    await connect_robust(**self._connection_kwargs),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aio_pika/robust_connection.py", line 377, in connect_robust
    await connection.connect(timeout=timeout)
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aio_pika/robust_connection.py", line 218, in connect
    await self.__fail_fast_future
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aio_pika/robust_connection.py", line 155, in __connection_factory
    await Connection.connect(self, self.__connect_timeout)
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aio_pika/connection.py", line 146, in connect
    self.transport = await UnderlayConnection.connect(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aio_pika/abc.py", line 731, in connect
    connection = await cls.make_connection(
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aio_pika/abc.py", line 715, in make_connection
    connection: aiormq.abc.AbstractConnection = await asyncio.wait_for(
                                                ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/asyncio/tasks.py", line 452, in wait_for
    return await fut
           ^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/connection.py", line 1014, in connect
    await connection.connect(client_properties or {})
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/base.py", line 164, in wrap
    return await self.create_task(func(self, *args, **kwargs))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/abc.py", line 46, in __inner
    raise self._exception from e
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/asyncio/tasks.py", line 694, in _wrap_awaitable
    return (yield from awaitable.__await__())
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/abc.py", line 46, in __inner
    raise self._exception from e
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/connection.py", line 601, in connect
    frame = await self._rpc(
            ^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/aiormq/connection.py", line 522, in _rpc
    raise AMQPInternalError(
pamqp.exceptions.AMQPInternalError: ("one of ['Connection.OpenOk']", <Connection.Close object at 0x7f4a8d598ad0>)

ERROR:    Application startup failed. Exiting.
