# Ana: Autonomous Event-Driven Agent

## Context

Ana is an event-driven, microservice-based AI system built with Hexagonal Architecture. It autonomously scrapes web data, processes RSS feeds, archives artifacts, and features a conversational AI loop, all orchestrated through a RabbitMQ event bus and backed by PostgreSQL.

The system is designed for complete environment isolation. You can run multiple separate "instances" (e.g., `devel`, `testing`, `prod`) on the same machine, each with its own dedicated database, RabbitMQ virtual host, and configuration files.

## Goal

After executing make provision INSTANCE=devel succesfully, I execute make run-configurator INSTANCE=devel and get the following message
Starting Interface (Port 8000) for instance: devel...
ANA_INSTANCE=devel uv run uvicorn apps.interface.src.interface.main:app --reload --port 8000
INFO:     Will watch for changes in these directories: ['/home/dberns/Projects/github/DanielBerns/ana']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [23337] using WatchFiles
{"payload": {"url": "http://localhost:8005/config/interface"}, "event": "fetching_configuration", "timestamp": "2026-03-30T01:54:19.816865Z"}
{"event": "config_fetched_successfully", "timestamp": "2026-03-30T01:54:19.901053Z"}
Process SpawnProcess-1:
Traceback (most recent call last):
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/multiprocessing/process.py", line 314, in _bootstrap
    self.run()
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/multiprocessing/process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/_subprocess.py", line 80, in subprocess_started
    target(sockets=sockets)
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/server.py", line 75, in run
    return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/_compat.py", line 30, in asyncio_run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/server.py", line 79, in serve
    await self._serve(sockets)
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/server.py", line 86, in _serve
    config.load()
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/config.py", line 441, in load
    self.loaded_app = import_from_string(self.app)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/.venv/lib/python3.11/site-packages/uvicorn/importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/.local/share/uv/python/cpython-3.11.11-linux-x86_64-gnu/lib/python3.11/importlib/__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1204, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 940, in exec_module
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
  File "/home/dberns/Projects/github/DanielBerns/ana/apps/interface/src/interface/main.py", line 17, in <module>
    DYNAMIC_CONFIG = fetch_dynamic_config("interface", logger)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/dberns/Projects/github/DanielBerns/ana/packages/shared/src/shared/config.py", line 40, in fetch_dynamic_config
    raise RuntimeError("Configuration missing 'rabbitmq_url'")
RuntimeError: Configuration missing 'rabbitmq_url'






This system is built to explore how to build a kind of intelligent agent based in a rule engine with an editable set of knowledge rules. I want a conversational AI loop, but I don't want to include LLM now.

## Goals

The goals are:
1. Redesign the Memory component, eliminating the dependence on an LLM provider, and including something like a stack, 
a content addressable memory, a tree based store (with uri like identifiers), or a simple random access memory (all these structures receiving and generating events)
2. Build a rule engine with an editable set of knowledge rules reacting to events.

I don't know how to build these things. I want suggestions, references of previous works, and remarks.
