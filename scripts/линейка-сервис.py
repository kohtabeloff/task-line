#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Служба «Линейка задач» — принимает правки со страницы и пишет их в файл задач.

Слушает 127.0.0.1:8040 (порт меняется ключом `--port`), наружу открывается через nginx
по секретному адресу — см. `deploy/nginx.conf.example`.

  GET  /api/state              — текущее состояние
  POST /api/toggle {p,t,done}  — отметить / вернуть задачу
  POST /api/add    {p,text}    — добавить задачу в конец линии проекта
  POST /api/del    {p,t}       — удалить задачу
  POST /api/edit   {p,t,text}  — изменить текст задачи
  POST /api/move   {p,from,to} — переставить задачу в другое место
  POST /api/moveproj {from,to} — переставить проект
  POST /api/fold   {p,свернут} — скрыть / показать задачи проекта
  POST /api/addproj{название}  — добавить проект

После каждой правки: файл задач -> генерация страницы. Если папка лежит в git и задан
ключ `--git`, изменения ещё и коммитятся с отправкой в репозиторий.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.environ.get("LINE_SRC") or os.path.join(ROOT, "данные", "линейка.yaml")
GEN = os.path.join(HERE, "линейка.py")
OUT = os.environ.get("LINE_OUT") or os.path.join(ROOT, "index.html")
PORT = int(os.environ.get("LINE_PORT") or 8040)
GIT_PUSH = (os.environ.get("LINE_GIT") or "0") == "1"
LOCK = threading.Lock()

HEADER = [
    "# Линейка задач. Порядок строк = порядок на линии.",
    "# Первая задача без «сделано: да» — та, что сейчас. Закрыл — поставь «сделано: да», линия сдвинется сама.",
]


def pick(d, *keys, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default


def is_done(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("да", "yes", "true", "1", "y", "истина")


def load():
    with open(SRC, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    st = {"обновлено": str(pick(data, "обновлено", "updated", default="") or ""), "проекты": []}
    for p in pick(data, "проекты", "projects", default=[]) or []:
        tasks = []
        for t in pick(p, "задачи", "tasks", default=[]) or []:
            if isinstance(t, dict):
                tasks.append({"текст": str(pick(t, "текст", "text", default="")),
                              "сделано": is_done(pick(t, "сделано", "done", default=False))})
            else:
                tasks.append({"текст": str(t), "сделано": False})
        st["проекты"].append({"название": str(pick(p, "название", "name", default="")),
                              "свернут": is_done(pick(p, "свернут", "folded", default=False)),
                              "задачи": tasks})
    return st


def q(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


def dump(st):
    out = list(HEADER) + ["", "обновлено: %s" % st["обновлено"], "", "проекты:"]
    for p in st["проекты"]:
        out.append('  - название: "%s"' % q(p["название"]))
        if p.get("свернут"):
            out.append("    свернут: да")
        if p["задачи"]:
            out.append("    задачи:")
            for t in p["задачи"]:
                out.append('      - текст: "%s"' % q(t["текст"]))
                if t["сделано"]:
                    out.append("        сделано: да")
        else:
            out.append("    задачи: []")
    return "\n".join(out) + "\n"


def git(*args, check=False):
    return subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True, check=check)


def publish(st):
    """Записать файл задач и собрать страницу. Если включён `--git` — ещё и отправить в репозиторий."""
    with open(SRC, "w", encoding="utf-8") as f:
        f.write(dump(st))

    gen = subprocess.run([sys.executable, GEN, "--src", SRC, "--out", OUT],
                         capture_output=True, text=True)
    if gen.returncode != 0:
        print("генерация упала:", gen.stderr, file=sys.stderr)

    if not GIT_PUSH:
        return
    git("pull", "-q", "--rebase")
    git("add", SRC)
    c = git("-c", "user.name=линейка", "-c", "user.email=line@local",
            "commit", "-q", "-m", "Линейка: правка со страницы")
    if c.returncode != 0 and "nothing to commit" not in c.stdout:
        print("commit:", c.stderr.strip(), file=sys.stderr)
    p = git("push", "-q", "origin", "HEAD")
    if p.returncode != 0:
        git("pull", "-q", "--rebase")
        p = git("push", "-q", "origin", "HEAD")
        if p.returncode != 0:
            print("push:", p.stderr.strip(), file=sys.stderr)


def apply_action(body):
    act = body.get("act")
    st = load()
    prj = st["проекты"]

    if act == "toggle":
        p, t = int(body["p"]), int(body["t"])
        prj[p]["задачи"][t]["сделано"] = bool(body["done"])
    elif act == "add":
        p = int(body["p"])
        text = str(body.get("text", "")).strip()
        if not text:
            raise ValueError("пустая задача")
        prj[p]["задачи"].append({"текст": text, "сделано": False})
    elif act == "del":
        p, t = int(body["p"]), int(body["t"])
        prj[p]["задачи"].pop(t)
    elif act == "move":
        p = int(body["p"])
        tasks = prj[p]["задачи"]
        f = int(body["from"])
        to = int(body["to"])
        if not (0 <= f < len(tasks)):
            raise ValueError("нет такой задачи")
        item = tasks.pop(f)
        to = max(0, min(to, len(tasks)))
        tasks.insert(to, item)
    elif act == "edit":
        p, t = int(body["p"]), int(body["t"])
        text = str(body.get("text", "")).strip()
        if not text:
            raise ValueError("пустой текст")
        prj[p]["задачи"][t]["текст"] = text
    elif act == "moveproj":
        f = int(body["from"])
        to = int(body["to"])
        if not (0 <= f < len(prj)):
            raise ValueError("нет такого проекта")
        item = prj.pop(f)
        to = max(0, min(to, len(prj)))
        prj.insert(to, item)
    elif act == "fold":
        p = int(body["p"])
        prj[p]["свернут"] = bool(pick(body, "свернут", "folded", default=True))
    elif act == "addproj":
        name = str(body.get("название", "")).strip()
        if not name:
            raise ValueError("пустое название")
        prj.append({"название": name, "свернут": False, "задачи": []})
    else:
        raise ValueError("неизвестное действие: %r" % act)

    st["обновлено"] = date.today().strftime("%d.%m.%Y")
    publish(st)
    return st


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/state"):
            self._send(200, load())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._send(400, {"error": "плохой запрос: %s" % e})
            return
        try:
            with LOCK:
                if "act" not in body:
                    body["act"] = self.path.rstrip("/").rsplit("/", 1)[-1]
                st = apply_action(body)
            self._send(200, st)
        except Exception as e:
            self._send(400, {"error": str(e)})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    global SRC, OUT, PORT, GIT_PUSH
    ap = argparse.ArgumentParser(description="Служба правок «Линейка задач»")
    ap.add_argument("--src", default=SRC, help="файл задач (по умолчанию данные/линейка.yaml)")
    ap.add_argument("--out", default=OUT, help="куда собирать страницу")
    ap.add_argument("--port", type=int, default=PORT, help="порт на 127.0.0.1 (по умолчанию 8040)")
    ap.add_argument("--git", action="store_true",
                    help="коммитить и отправлять файл задач в репозиторий (если папка в git)")
    a = ap.parse_args()
    SRC, OUT, PORT, GIT_PUSH = a.src, a.out, a.port, a.git
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("линейка-сервис слушает 127.0.0.1:%d" % PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()