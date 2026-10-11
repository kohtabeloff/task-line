#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Страница «Линейка задач» — собирается из файла задач (по умолчанию данные/линейка.yaml).

Запуск:
    python3 scripts/линейка.py --out /var/www/task-line/index.html
Без аргументов пишет в /tmp/линейка.html (для предпросмотра).

На широком экране линия горизонтальная, на телефоне — вертикальная.
Правки (отметить, вернуть, добавить, переставить) уходят в службу линейка-сервис.py.
"""
import argparse
import hashlib
import html
import json
import os
import sys
from datetime import date

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SRC = os.path.join(ROOT, "данные", "линейка.yaml")


def pick(d, *keys, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default


def is_done(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("да", "yes", "true", "1", "y", "истина")


def load_state(src):
    with open(src, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    projects = []
    for p in pick(data, "проекты", "projects", default=[]) or []:
        tasks = []
        for t in pick(p, "задачи", "tasks", default=[]) or []:
            if isinstance(t, dict):
                tasks.append({
                    "текст": str(pick(t, "текст", "text", default="")),
                    "сделано": is_done(pick(t, "сделано", "done", default=False)),
                })
            else:
                tasks.append({"текст": str(t), "сделано": False})
        projects.append({
            "название": str(pick(p, "название", "name", default="Без названия")),
            "свернут": is_done(pick(p, "свернут", "folded", default=False)),
            "задачи": tasks,
        })
    upd = str(pick(data, "обновлено", "updated", default="") or "").strip()
    return {"обновлено": upd, "проекты": projects}


CSS = """
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:#0e0e0f;color:#ececee;
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.page{max-width:1180px;margin:0 auto;padding:26px 20px 70px;
 padding-top:calc(12px + env(safe-area-inset-top,0px))}
header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
 flex-wrap:wrap;padding:10px 0 0;margin:0 0 22px}
h1{font-size:19px;font-weight:650;margin:0;letter-spacing:.005em}
.sub{font-size:12px;color:#6d6d76}
.prj{position:relative;margin:0 0 34px}
.phead{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 14px;
 cursor:grab}
body.dragmode .phead{cursor:grabbing}
.foldbtn{border:0;background:transparent;color:#8d8d96;cursor:pointer;font-family:inherit;
 font-size:15px;line-height:1;width:20px;height:20px;padding:0 0 2px;margin:0 6px 0 0;
 border-radius:6px;vertical-align:middle;transition:color .15s,background .15s}
.foldbtn:hover{color:#E60023;background:rgba(230,0,35,.10)}
.prj.dragging{opacity:.55;pointer-events:none}
.prj.dragging .phead{cursor:grabbing}
.prj.drop-top::before,.prj.drop-bottom::after{content:"";position:absolute;left:0;right:0;height:3px;
 background:#E60023;border-radius:2px;z-index:2}
.prj.drop-top::before{top:-7px}
.prj.drop-bottom::after{bottom:-8px}
.ptitle{font-size:13px;color:#8d8d96;font-weight:560;letter-spacing:.01em;display:flex;align-items:center}
.pcount{font-size:11.5px;color:#66666f;white-space:nowrap}
.bar{height:3px;background:#242428;border-radius:2px;overflow:hidden;margin:0 0 16px}
.bar>i{display:block;height:100%;background:#E60023;border-radius:2px;transition:width .35s ease}
.rail{display:flex;align-items:stretch;overflow-x:auto;padding:2px 0 12px;
 scrollbar-width:thin;scroll-snap-type:x proximity}
.rail::-webkit-scrollbar{height:8px}
.rail::-webkit-scrollbar-thumb{background:#2c2c31;border-radius:4px}
.railwrap{position:relative}
.railwrap::after{content:"";position:absolute;right:0;top:0;bottom:14px;width:54px;pointer-events:none;
 background:linear-gradient(90deg,rgba(14,14,15,0),#0e0e0f 78%);opacity:0;transition:opacity .25s}
.railwrap.ovf::after{opacity:1}
.railwrap.ovf.atend::after{opacity:0}
.step{position:relative;flex:0 0 auto;width:196px;margin-right:13px;
 background:#16161a;border:1px solid #26262c;border-radius:13px;padding:12px 13px 13px;
 cursor:pointer;scroll-snap-align:start;transition:border-color .18s,transform .18s,background .18s}
.step:hover{border-color:#3a3a44;transform:translateY(-1px)}
.step:last-child{margin-right:0}
.step .t{font-size:13.5px;line-height:19px;display:block;padding-right:20px}
.step .num{font-size:10.5px;color:#5b5b64;display:block;margin:0 0 6px;letter-spacing:.06em;
 padding-right:30px}
.step.done{background:#141417;border-color:#212127}
.step.done .t{color:#7d7d88;text-decoration:line-through}
.step.done .num{color:#60606a}
.step.done .num::after{content:" · сделано"}
.step.now{border-color:#E60023;background:rgba(230,0,35,.09)}
.step.now .t{font-weight:640;color:#fff}
.step.now .num{color:#E60023;font-weight:700;letter-spacing:.09em}
.step .tools{position:absolute;top:4px;right:5px;display:flex;gap:2px;align-items:center}
.step .tools button{border:0;border-radius:6px;background:transparent;color:#6a6a75;cursor:pointer;
 line-height:1;padding:0;width:20px;height:20px;font-size:14px;opacity:.45;
 transition:opacity .15s,color .15s,background .15s}
.step .tools .del{font-size:16px}
.step:hover .tools button{opacity:1}
.step .tools button:hover{color:#E60023;background:rgba(230,0,35,.12)}
.step .tools button:disabled{opacity:.12;cursor:default;background:transparent;color:#6a6a75}
.step.ask{border-color:#E60023;box-shadow:0 0 0 2px rgba(230,0,35,.30)}
.step.ask .num{color:#E60023}
.step.ask .t{color:#fff}
.step.editing{cursor:default;width:250px}
.step.editing textarea{width:100%;min-height:58px;resize:vertical;background:#0f0f12;color:#ececee;
 border:1px solid #2a2a31;border-radius:8px;padding:7px;font-family:inherit;font-size:13px;line-height:18px}
.step.editing .erow{display:flex;gap:6px;margin-top:7px;justify-content:flex-end}
.step.editing .erow button{font-family:inherit;font-size:12px;padding:5px 10px;border-radius:8px;cursor:pointer;
 border:1px solid #2f2f37;background:#1d1d22;color:#d8d8df}
.step.editing .erow button.ok{background:#E60023;border-color:#E60023;color:#fff;font-weight:600}
.step{user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}
.step.dragging{border-color:#E60023;transform:scale(1.03);
 box-shadow:0 0 0 2px rgba(230,0,35,.35),0 10px 24px rgba(0,0,0,.5);z-index:3}
.step.drop-before::after,.step.drop-after::after{content:"";position:absolute;top:0;bottom:0;
 width:3px;background:#E60023;border-radius:2px;z-index:2}
.step.drop-before::after{left:-8px}
.step.drop-after::after{right:-8px}
.hint{font-size:11.5px;color:#5f5f68;margin-left:12px}
body.dragmode{cursor:grabbing}
body.dragmode .step{transition:none}
.step.dragging{pointer-events:none}
.addbtn{flex:0 0 auto;width:212px;border:1px dashed #33333b;border-radius:13px;background:transparent;
 color:#77777f;font-size:13px;font-family:inherit;cursor:pointer;padding:12px;
 transition:border-color .18s,color .18s;align-self:stretch}
.addbtn:hover{border-color:#4a4a56;color:#c9c9d1}
.addbox{flex:0 0 auto;width:212px;background:#16161a;border:1px solid #E60023;border-radius:13px;
 padding:10px}
.addbox textarea{width:100%;min-height:56px;resize:vertical;background:#0f0f12;color:#ececee;
 border:1px solid #2a2a31;border-radius:8px;padding:8px;font-family:inherit;font-size:13px}
.addbox .row{display:flex;gap:6px;margin-top:7px;justify-content:flex-end}
.addbox button{font-family:inherit;font-size:12px;padding:6px 11px;border-radius:8px;cursor:pointer;
 border:1px solid #2f2f37;background:#1d1d22;color:#d8d8df}
.addbox button.ok{background:#E60023;border-color:#E60023;color:#fff;font-weight:600}
footer{margin-top:34px;display:flex;gap:10px;flex-wrap:wrap}
footer button{font-family:inherit;font-size:12.5px;padding:9px 14px;border-radius:10px;cursor:pointer;
 border:1px dashed #33333b;background:transparent;color:#7a7a83}
footer button:hover{border-color:#4a4a56;color:#c9c9d1}
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);
 background:#1c1c21;border:1px solid #33333b;color:#e6e6ec;padding:10px 16px;border-radius:10px;
 font-size:13px;opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;z-index:9}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.empty{color:#6d6d76;font-size:13.5px;padding:6px 0 14px}
@media (max-width:700px){
 .page{padding:calc(10px + env(safe-area-inset-top,0px)) 15px calc(60px + env(safe-area-inset-bottom,0px))}
 .addbox textarea{font-size:16px}
 .step.editing{width:100%}
 .step.editing textarea{font-size:16px}
 .step .tools button{opacity:.8}
 .rail{flex-direction:column;overflow:visible;padding:0 0 0 26px;position:relative;
  scroll-snap-type:none}
 .rail::before{content:"";position:absolute;left:7px;top:18px;bottom:22px;width:2px;
  background:#26262c;border-radius:2px}
 .railwrap::after{display:none}
 .step,.addbtn,.addbox{width:100%;margin:0 0 10px}
 .step{padding-left:15px}
 .step:before{content:"";position:absolute;left:-24px;top:22px;width:8px;height:8px;border-radius:50%;
  box-sizing:content-box;background:#3a3a44;border:2px solid #0e0e0f}
 .step.done:before{background:#2f2f37}
 .step.now:before{background:#E60023}
 .step.drop-before::after,.step.drop-after::after{width:auto;height:3px;left:0;right:0;top:auto;bottom:auto}
 .step.drop-before::after{top:-6px}
 .step.drop-after::after{bottom:-6px}
}
@media (prefers-color-scheme:light){
 header{background:#fafafb}
 body{background:#fafafb;color:#1a1a1e}
 h1{color:#111}.sub,.empty,.pcount{color:#7c7c85}
 .ptitle{color:#6f6f78}
 .foldbtn{color:#8a8a93}
 .bar{background:#e6e6ea}
 .step{background:#fff;border-color:#e4e4e9}
 .step.done{background:#f5f5f7;border-color:#ececf0}
 .step.done .t{color:#a8a8b1}
 .step.now{background:rgba(230,0,35,.05)}
 .step.now .t{color:#111}
 .rail::before{background:#e6e6ea}
 .step:before{background:#d7d7df;border-color:#fafafb}
 .step.done:before{background:#e6e6ea}
 .railwrap::after{background:linear-gradient(90deg,rgba(250,250,251,0),#fafafb 78%)}
 .addbtn,footer button{color:#7c7c85}
 .addbox{background:#fff}.addbox textarea{background:#fafafb;color:#1a1a1e;border-color:#e4e4e9}
 .addbox button{background:#f2f2f5;color:#3a3a42;border-color:#e0e0e6}
 .step.editing textarea{background:#fafafb;color:#1a1a1e;border-color:#e4e4e9}
 .step.editing .erow button{background:#f2f2f5;color:#3a3a42;border-color:#e0e0e6}
 .toast{background:#fff;color:#1a1a1e;border-color:#e4e4e9}
}
"""

TPL = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Задачи</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Задачи">
<meta name="theme-color" content="#0e0e0f">
<link rel="apple-touch-icon" href="icon.png">
<link rel="icon" href="icon.png">
<style>__CSS__</style>
</head>
<body data-build="__VER__">
<div class="page">
<header><h1>Задачи</h1><div class="sub">обновлено __SUB__</div></header>
<main id="app"></main>
<footer>
  <button type="button" onclick="addProject()">+ новый проект</button>
  <span class="hint">зажми задачу или название проекта и потяни — переставить · стрелка у названия скрывает задачи</span>
</footer>
</div>
<script id="state" type="application/json">__DATA__</script>
<script>
const API = "api/";
let S = JSON.parse(document.getElementById("state").textContent);
let edit = null;       // {p, mode:"add"}
let editTask = null;   // {p,t} — задача, у которой правим текст
let pending = false;
let ask = null;        // {p,t} — задача, ждущая второго тапа
let askTimer = null;

function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML;}

function render(){
  const app = document.getElementById("app");
  let h = "";
  S.проекты.forEach((p, pi) => {
    const total = p.задачи.length;
    const done = p.задачи.filter(t => t.сделано).length;
    let firstOpen = p.задачи.findIndex(t => !t.сделано);
    const pct = total ? Math.round(done/total*100) : 0;
    const folded = !!p.свернут;
    h += '<section class="prj" data-p="' + pi + '">';
    h += '<div class="phead"><div class="ptitle">'
       + '<button class="foldbtn" title="' + (folded ? "показать" : "скрыть") + '"'
       + ' onclick="fold(event,' + pi + ')">' + (folded ? "▸" : "▾") + '</button>'
       + esc(p.название) + '</div>'
       + '<div class="pcount">' + done + " из " + total + '</div></div>';
    h += '<div class="bar"><i style="width:' + pct + '%"></i></div>';
    if (!folded) {
    h += '<div class="railwrap"><div class="rail">';
    p.задачи.forEach((t, ti) => {
      const asking = ask && ask.p === pi && ask.t === ti;
      const editing = editTask && editTask.p === pi && editTask.t === ti;
      let cls = t.сделано ? "step done" : (ti === firstOpen ? "step now" : "step");
      if (asking) cls += " ask";
      if (editing) cls += " editing";
      const lbl = asking ? "ТАПНИ ЕЩЁ РАЗ"
                : (t.сделано ? "ГОТОВО" : (ti === firstOpen ? "СЕЙЧАС" : "ДАЛЬШЕ"));
      let inner;
      if (editing) {
        inner = '<textarea id="te">' + esc(t.текст) + '</textarea>'
              + '<div class="erow"><button onclick="editTask=null;render()">Отмена</button>'
              + '<button class="ok" onclick="submitEdit(' + pi + ',' + ti + ')">Сохранить</button></div>';
      } else {
        inner = '<span class="num">' + lbl + '</span>'
              + '<span class="t">' + esc(t.текст) + '</span>'
              + '<span class="tools">'
              + '<button class="pen" title="изменить" onclick="openEditTask(event,' + pi + ',' + ti + ')">&#9998;</button>'
              + '<button class="del" title="удалить" onclick="del(event,' + pi + ',' + ti + ')">&times;</button>'
              + '</span>';
      }
      h += '<div class="' + cls + '" data-p="' + pi + '" data-t="' + ti + '"'
         + (editing ? '' : ' onclick="toggle(' + pi + ',' + ti + ')"')
         + '>' + inner + '</div>';
    });
    if (edit && edit.p === pi) {
      h += '<div class="addbox"><textarea id="ta" placeholder="Что нужно сделать?"></textarea>'
         + '<div class="row"><button onclick="edit=null;render()">Отмена</button>'
         + '<button class="ok" onclick="submitAdd(' + pi + ')">Добавить</button></div></div>';
    } else {
      h += '<button class="addbtn" onclick="openAdd(' + pi + ')">+ задача</button>';
    }
    h += '</div></div>';
    }
    h += '</section>';
  });
  if (!S.проекты.length) h = '<div class="empty">пока пусто — нажми «+ новый проект»</div>';
  app.innerHTML = h;
  attachRails();
  document.querySelectorAll(".step").forEach(el => el.addEventListener("pointerdown", stepDown));
  document.querySelectorAll(".phead").forEach(el => el.addEventListener("pointerdown", prjDown));
  if (edit) { const ta = document.getElementById("ta"); if (ta) ta.focus(); }
  if (editTask) { const te = document.getElementById("te"); if (te) { te.focus(); te.setSelectionRange(te.value.length, te.value.length);
      te.addEventListener("keydown", function(ev){ if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); submitEdit(editTask.p, editTask.t); } }); } }
}

function attachRails(){
  document.querySelectorAll(".railwrap").forEach(w => {
    const r = w.querySelector(".rail");
    if (!r) return;
    const upd = () => {
      const ovf = r.scrollWidth - r.clientWidth > 4;
      w.classList.toggle("ovf", ovf);
      w.classList.toggle("atend", !ovf || r.scrollLeft + r.clientWidth >= r.scrollWidth - 6);
    };
    r.addEventListener("scroll", upd, {passive:true});
    upd();
  });
}

function toast(msg){
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("on");
  clearTimeout(toast._h); toast._h = setTimeout(() => t.classList.remove("on"), 2600);
}

async function call(path, body){
  const r = await fetch(API + path, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function apply(newState){ S = newState; render(); }

async function toggle(pi, ti){
  if (justDragged) { justDragged = false; return; }   // это был перенос, а не тап
  if (ask && ask.p === pi && ask.t === ti) {          // второй тап — применяем
    clearTimeout(askTimer); ask = null;
    if (pending) return;
    pending = true;
    const t = S.проекты[pi].задачи[ti];
    try { apply(await call("toggle", {p: pi, t: ti, done: !t.сделано})); }
    catch (e) { toast("Не сохранилось — проверь связь"); }
    pending = false;
    return;
  }
  ask = {p: pi, t: ti};                               // первый тап — спрашиваем
  clearTimeout(askTimer);
  askTimer = setTimeout(() => { ask = null; render(); }, 4000);
  render();
}

async function move(ev, pi, ti, to){
  if (ev && ev.stopPropagation) ev.stopPropagation();
  if (pending || pi === null || pi === undefined) return;
  pending = true;
  try { apply(await call("move", {p: pi, from: ti, to: to})); }
  catch (e) { toast("Не переставилось — проверь связь"); }
  pending = false;
}

// — перенос: зажал задачу и потянул (палец или мышь) —
let hold = null;
let justDragged = false;

function stepDown(ev){
  if (ev.button && ev.button !== 0) return;
  if (ev.target.closest("button,textarea,input")) return;
  if (pending) return;
  const card = ev.currentTarget;
  clearHold();
  hold = {pi: +card.dataset.p, ti: +card.dataset.t, el: card,
          x: ev.clientX, y: ev.clientY, active: false,
          timer: setTimeout(startHold, ev.pointerType === "mouse" ? 130 : 380)};
}

function startHold(){
  if (!hold) return;
  hold.active = true;
  justDragged = true;
  hold.el.classList.add("dragging");
  document.body.classList.add("dragmode");
  try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) {}
}

function stepMove(ev){
  if (!hold) return;
  const dx = ev.clientX - hold.x, dy = ev.clientY - hold.y;
  if (!hold.active) {
    if (Math.hypot(dx, dy) > 8) clearHold();     // это прокрутка, а не перенос
    return;
  }
  ev.preventDefault();
  paintDrop(hitInfo(ev.clientX, ev.clientY, hold.pi, hold.ti));
}

function stepUp(ev){
  if (!hold) return;
  const h = hold; hold = null;
  clearTimeout(h.timer);
  h.el.classList.remove("dragging");
  document.body.classList.remove("dragmode");
  clearDrop();
  if (!h.active) { setTimeout(() => { justDragged = false; }, 40); return; }
  const hit = hitInfo(ev.clientX, ev.clientY, h.pi, h.ti);
  if (!hit) return;
  const to = hit.before ? (h.ti < hit.t ? hit.t - 1 : hit.t)
                        : (h.ti < hit.t ? hit.t : hit.t + 1);
  if (to === h.ti) return;
  move(null, h.pi, h.ti, to);
}

function clearHold(){ if (hold) clearTimeout(hold.timer); hold = null; }

function cardUnder(x, y){
  const el = document.elementFromPoint(x, y);
  return el ? el.closest(".step") : null;
}

// Куда встанет: над какой карточкой палец и с какой стороны — до неё или после
function hitInfo(x, y, pi, ti){
  const el = cardUnder(x, y);
  if (!el || +el.dataset.p !== pi || +el.dataset.t === ti) return null;
  const r = el.getBoundingClientRect();
  const horizontal = window.innerWidth > 700;
  const before = horizontal ? (x < r.left + r.width / 2) : (y < r.top + r.height / 2);
  return {t: +el.dataset.t, before: before};
}

function paintDrop(hit){
  clearDrop();
  if (!hit) return;
  const el = document.querySelector('.step[data-p="' + hold.pi + '"][data-t="' + hit.t + '"]');
  if (el) el.classList.add(hit.before ? "drop-before" : "drop-after");
}

function clearDrop(){
  document.querySelectorAll(".step.drop-before,.step.drop-after")
    .forEach(el => el.classList.remove("drop-before", "drop-after"));
}

// — свернуть / показать задачи проекта —
async function fold(ev, pi){
  if (ev && ev.stopPropagation) ev.stopPropagation();
  if (pending) return;
  pending = true;
  const cur = !!S.проекты[pi].свернут;
  try { apply(await call("fold", {p: pi, "свернут": !cur})); }
  catch (e) { toast("Не сохранилось — проверь связь"); }
  pending = false;
}

// — перенос проекта: зажал название и потянул вверх/вниз —
let phold = null;

function prjDown(ev){
  if (ev.button && ev.button !== 0) return;
  if (ev.target.closest("button")) return;
  if (pending) return;
  const sec = ev.currentTarget.closest(".prj");
  if (!sec) return;
  clearPHold();
  phold = {pi: +sec.dataset.p, el: sec, x: ev.clientX, y: ev.clientY, active: false,
           timer: setTimeout(startPHold, ev.pointerType === "mouse" ? 130 : 380)};
}

function startPHold(){
  if (!phold) return;
  phold.active = true;
  justDragged = true;
  phold.el.classList.add("dragging");
  document.body.classList.add("dragmode");
  try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) {}
}

function prjMove(ev){
  if (!phold) return;
  const dx = ev.clientX - phold.x, dy = ev.clientY - phold.y;
  if (!phold.active) {
    if (Math.hypot(dx, dy) > 8) clearPHold();
    return;
  }
  ev.preventDefault();
  paintPDrop(projHit(ev.clientX, ev.clientY, phold.pi));
}

function prjUp(ev){
  if (!phold) return;
  const h = phold; phold = null;
  clearTimeout(h.timer);
  h.el.classList.remove("dragging");
  document.body.classList.remove("dragmode");
  clearPDrop();
  if (!h.active) { setTimeout(() => { justDragged = false; }, 40); return; }
  const hit = projHit(ev.clientX, ev.clientY, h.pi);
  if (!hit) return;
  const to = hit.before ? (h.pi < hit.p ? hit.p - 1 : hit.p)
                        : (h.pi < hit.p ? hit.p : hit.p + 1);
  if (to === h.pi) return;
  moveProj(h.pi, to);
}

function clearPHold(){ if (phold) clearTimeout(phold.timer); phold = null; }

function projHit(x, y, pi){
  const el = document.elementFromPoint(x, y);
  const sec = el ? el.closest(".prj") : null;
  if (!sec || +sec.dataset.p === pi) return null;
  const r = sec.getBoundingClientRect();
  return {p: +sec.dataset.p, before: y < r.top + r.height / 2};
}

function paintPDrop(hit){
  clearPDrop();
  if (!hit) return;
  const el = document.querySelector('.prj[data-p="' + hit.p + '"]');
  if (el) el.classList.add(hit.before ? "drop-top" : "drop-bottom");
}

function clearPDrop(){
  document.querySelectorAll(".prj.drop-top,.prj.drop-bottom")
    .forEach(el => el.classList.remove("drop-top", "drop-bottom"));
}

async function moveProj(from, to){
  if (pending) return;
  pending = true;
  try { apply(await call("moveproj", {from: from, to: to})); }
  catch (e) { toast("Не переставилось — проверь связь"); }
  pending = false;
}

async function del(ev, pi, ti){
  ev.stopPropagation();
  if (!confirm("Удалить эту задачу?")) return;
  try { apply(await call("del", {p: pi, t: ti})); }
  catch (e) { toast("Не удалилось — проверь связь"); }
}

function openAdd(pi){ edit = {p: pi}; editTask = null; render(); }

// — правка текста задачи —
function openEditTask(ev, pi, ti){
  if (ev && ev.stopPropagation) ev.stopPropagation();
  ask = null; clearTimeout(askTimer);
  edit = null;
  editTask = {p: pi, t: ti};
  render();
}

async function submitEdit(pi, ti){
  const el = document.getElementById("te");
  const text = ((el && el.value) || "").trim();
  if (!text) { editTask = null; render(); return; }
  if (pending) return;
  pending = true;
  try { apply(await call("edit", {p: pi, t: ti, text: text})); editTask = null; }
  catch (e) { toast("Не сохранилось — проверь связь"); }
  pending = false;
}

async function submitAdd(pi){
  const ta = document.getElementById("ta");
  const text = (ta.value || "").trim();
  if (!text) { edit = null; render(); return; }
  try { apply(await call("add", {p: pi, text: text})); edit = null; }
  catch (e) { toast("Не добавилось — проверь связь"); }
}

async function addProject(){
  const name = prompt("Название проекта");
  if (!name || !name.trim()) return;
  try { apply(await call("addproj", {название: name.trim()})); }
  catch (e) { toast("Не добавилось — проверь связь"); }
}

// Свежесть: вернулся в приложение — подтягиваем новую версию, если задачи изменились
async function checkFresh(){
  try{
    const r = await fetch(location.pathname, {cache:"no-store"});
    const t = await r.text();
    const m = t.match(/data-build="([^"]+)"/);
    if (m && m[1] !== document.body.dataset.build) location.reload();
  }catch(e){}
}
document.addEventListener("visibilitychange", function(){ if (!document.hidden) checkFresh(); });
window.addEventListener("focus", checkFresh);

document.addEventListener("pointermove", function(ev){ stepMove(ev); prjMove(ev); }, {passive:false});
document.addEventListener("pointerup", function(ev){ stepUp(ev); prjUp(ev); });
document.addEventListener("pointercancel", function(){
  if (hold) { hold.el.classList.remove("dragging"); clearHold(); }
  if (phold) { phold.el.classList.remove("dragging"); clearPHold(); }
  document.body.classList.remove("dragmode");
});
document.addEventListener("touchmove", function(ev){ if ((hold && hold.active) || (phold && phold.active)) ev.preventDefault(); }, {passive:false});

render();
</script>
</body>
</html>
"""


def make_icon(path, size=180):
    """Простая иконка: три полосы, средняя — акцент. Пишем PNG без библиотек."""
    import struct
    import zlib

    bg = (17, 17, 18)
    bar = (214, 214, 216)
    acc = (230, 0, 35)
    bars = [(48, bar), (84, acc), (120, bar)]
    x0, x1, h = 40, 140, 12

    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            c = bg
            for by, bc in bars:
                if by <= y < by + h and x0 <= x < x1:
                    c = bc
            row += bytes(c)
        rows.append(bytes(row))

    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def build(src):
    st = load_state(src)
    sub = st["обновлено"] or date.today().strftime("%d.%m.%Y")
    data = json.dumps(st, ensure_ascii=False).replace("</", "<\\/")
    ver = hashlib.sha1(data.encode("utf-8")).hexdigest()[:10]
    return (TPL.replace("__CSS__", CSS)
               .replace("__SUB__", html.escape(sub))
               .replace("__VER__", ver)
               .replace("__DATA__", data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default="/tmp/линейка.html")
    a = ap.parse_args()

    out = build(a.src)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(out)
    make_icon(os.path.join(os.path.dirname(os.path.abspath(a.out)), "icon.png"))
    n = len(load_state(a.src)["проекты"])
    print("готово: %s (%d байт, проектов: %d)" % (a.out, len(out.encode("utf-8")), n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
