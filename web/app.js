/* 말한대로 화면. 빌드 단계 없이 그대로 도는 한 파일. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var DAYS = ["일", "월", "화", "수", "목", "금", "토"];
  var KIND = { call: "통화", meeting: "회의", memo: "내 메모", file: "파일", photo: "사진" };
  var STATUS = { received: "받았어요", transcribing: "글로 바꾸는 중", ready: "준비됨", extracting: "챙길 것 찾는 중", extracted: "다 적어 뒀어요", failed: "못 했어요" };
  var state = { me: null, date: null, today: null, tab: "today", poll: null };

  /* ---------- 도우미 ---------- */
  function api(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", credentials: "same-origin", headers: {} };
    if (opts.json !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.json); }
    if (opts.form) init.body = opts.form;
    return fetch(path, init).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        if (!r.ok) { var e = new Error(body.detail || "지금은 연결이 안 돼요. 잠시 뒤에 다시 해 주세요."); e.status = r.status; throw e; }
        return body;
      });
    }, function () { throw new Error("서버에 닿지 못했어요. 집 PC가 켜져 있는지 확인해 주세요."); });
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function btn(label, cls, fn) { var b = el("button", cls, label); b.type = "button"; b.addEventListener("click", fn); return b; }
  function ymd(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function toDate(s) { var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function shift(s, n) { var d = toDate(s); d.setDate(d.getDate() + n); return ymd(d); }
  function nice(s) { var d = toDate(s); return (d.getMonth() + 1) + "월 " + d.getDate() + "일 " + DAYS[d.getDay()] + "요일"; }
  function say(id, text, err) { var n = $(id); n.textContent = text || ""; n.className = "msg" + (err ? " err" : ""); }
  function fail(id) { return function (e) { say(id, e.message, true); }; }

  /* ---------- 들어오기 ---------- */
  var params = new URLSearchParams(location.search);
  var invite = params.get("invite") || "";
  if (invite) { $("join-code").hidden = true; $("join-code-label").hidden = true; $("join-invited").hidden = false; }
  if (params.get("link") === "expired") say("join-msg", "QR의 시간이 지났어요. PC에서 QR을 다시 받아 주세요.", true);
  function boot() {
    api("/api/me").then(function (me) {
      state.me = me; state.today = me.today; state.date = state.date || me.today;
      $("v-join").hidden = true; $("v-main").hidden = false;
      $("who").textContent = me.name + " 님";
      var q = new URLSearchParams(location.search).get("shared");
      if (q) { say("in-msg", q === "0" ? "받을 내용이 없었어요." : q + "건 받았어요. 챙길 것을 찾고 있어요."); history.replaceState(null, "", "/"); }
      if (params.get("link") === "ok") { history.replaceState(null, "", "/"); say("in-msg", "이 기기를 연결했어요."); }
      var cal = new URLSearchParams(location.search).get("cal");
      if (cal) {
        history.replaceState(null, "", "/"); $("cal-box").hidden = false; loadCal();
        if (cal !== "ok") $("cal-err").textContent = "구글 연결을 마치지 못했어요. 다시 눌러 주세요.";
      }
      if (me.ai === "none") say("in-msg", "AI가 연결되지 않아 아직 챙길 것을 뽑지 못해요. PC에 Claude Code를 설치해 로그인하거나 .env에 키를 넣어 주세요.", true);
      if (me.ai === "fake") say("in-msg", "지금은 흉내 모드예요. 화면 확인용이라 뽑기가 정확하지 않아요.");
      refresh();
    }).catch(function (e) {
      if (e.status === 401) { $("v-main").hidden = true; $("v-join").hidden = false; }
      else { $("v-join").hidden = false; say("join-msg", e.message, true); }
    });
  }
  $("join-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    api("/api/join", { method: "POST", json: { name: $("join-name").value, code: $("join-code").value, invite: invite } })
      .then(function () { if (invite) history.replaceState(null, "", "/"); boot(); }).catch(fail("join-msg"));
  });
  $("btn-leave").addEventListener("click", function () { api("/api/leave", { method: "POST" }).then(function () { location.reload(); }); });

  /* ---------- 항목 그리기 ---------- */
  function niceTime(t) {
    var p = t.split(":"), h = +p[0];
    return (h < 12 ? "오전 " : "오후 ") + (h % 12 === 0 ? 12 : h % 12) + ":" + p[1];
  }
  function shortDate(d) { var x = toDate(d); return (x.getMonth() + 1) + "/" + x.getDate() + "(" + DAYS[x.getDay()] + ")"; }
  function meta(it, kind) {
    var m = el("div", "meta");
    m.appendChild(el("span", "tag " + (it.scope === "회사" ? "work" : "home"), it.scope));
    if (it.owner === "unclear") m.appendChild(el("span", "tag carry", "누구 일인지 확인" + (it.who ? " · " + it.who : "")));
    if (it.status === "other" && it.who) m.appendChild(el("span", "tag", it.who));
    if (it.plan_time) m.appendChild(el("span", "tag when", niceTime(it.plan_time)));
    if (kind === "later" && it.due_date) m.appendChild(el("span", "tag when", shortDate(it.due_date) + " 기한"));
    else if (it.due_text) m.appendChild(el("span", "tag", it.due_text));
    if (it.carried_days > 0) m.appendChild(el("span", "tag carry", it.carried_days === 1 ? "어제에서 넘어옴" : it.carried_days + "일 넘어옴"));
    return m;
  }
  function setItem(it, body) { return api("/api/items/" + it.id, { method: "PATCH", json: body }).then(refresh).catch(fail("in-msg")); }
  function delItem(it) { return api("/api/items/" + it.id, { method: "DELETE" }).then(refresh).catch(fail("in-msg")); }
  function field(labelText, input) { var l = el("label", "fld", labelText); l.appendChild(input); return l; }
  function editForm(it) {
    /* 내용, 날짜, 시각을 한 곳에서 고친다 */
    var f = el("form", "edit"); f.hidden = true;
    var t = el("input"); t.value = it.text; t.maxLength = 200; t.required = true;
    var d = el("input"); d.type = "date"; d.value = it.plan_date || "";
    var tm = el("input"); tm.type = "time"; tm.value = it.plan_time || "";
    f.appendChild(field("할 일", t)); f.appendChild(field("날짜", d)); f.appendChild(field("시각 (안 정해도 돼요)", tm));
    var save = el("button", "primary small", "저장"); save.type = "submit"; f.appendChild(save);
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var body = { text: t.value, plan_time: tm.value };
      if (d.value) { body.status = "todo"; body.plan_date = d.value; }
      setItem(it, body);
    });
    return f;
  }
  function calendarRow(it) {
    /* 바깥 캘린더로 보내기. 시각은 '고치기'에서 정해 둔 것을 쓴다 */
    var box = el("div", "cal"); box.hidden = true;
    function go(which) {
      api("/api/items/" + it.id + "/calendar").then(function (r) {
        if (which === "google") window.open(r.google_url, "_blank", "noopener"); else location.href = r.ics_url;
      }).catch(fail("in-msg"));
    }
    var row = el("div", "row");
    row.appendChild(btn("구글 캘린더에 넣기", "", function () { go("google"); }));
    row.appendChild(btn("일정 파일 받기", "", function () { go("ics"); }));
    box.appendChild(row);
    box.appendChild(el("p", "msg", "일정 파일은 받은 뒤 열면 휴대폰의 캘린더 앱(삼성, 네이버 등)에 추가돼요."));
    return box;
  }
  function itemNode(it, kind) {
    /* 한 줄로 보이고, 눌러야 나머지 버튼이 펼쳐진다 */
    var li = el("li", "item" + (it.status === "done" ? " done" : ""));
    var head = el("div", "head");
    if (kind === "todo" || kind === "done") {
      var c = btn(it.status === "done" ? "✓" : "", "check" + (it.status === "done" ? " on" : ""), function () {
        setItem(it, it.status === "done" ? { status: "todo", plan_date: state.today } : { status: "done" });
      });
      c.setAttribute("aria-label", it.status === "done" ? "끝냄 취소" : "끝냄으로 표시");
      head.appendChild(c);
    }
    var more = el("div", "more"); more.hidden = true;
    var what = btn("", "what", function () { more.hidden = !more.hidden; what.setAttribute("aria-expanded", String(!more.hidden)); });
    what.setAttribute("aria-expanded", "false");
    what.appendChild(el("span", "txt", it.text)); what.appendChild(meta(it, kind));
    head.appendChild(what);
    var future = it.due_date && it.due_date > state.today;
    if (kind === "new" || kind === "due") {
      /* 가장 그럴듯한 선택 하나만 밖에 둔다 */
      head.appendChild(future
        ? btn(shortDate(it.due_date), "pick quick", function () { setItem(it, { status: "todo", plan_date: it.due_date }); })
        : btn("오늘", "pick quick", function () { setItem(it, { status: "todo", plan_date: state.today }); }));
    } else if (kind === "later") {
      head.appendChild(btn("오늘", "quick", function () { setItem(it, { status: "todo", plan_date: state.today }); }));
    }
    li.appendChild(head);
    if (kind === "done") { more.appendChild(el("p", "msg", "동그라미를 다시 누르면 끝냄을 취소해요.")); li.appendChild(more); return li; }

    if (kind === "new" && it.quote) more.appendChild(el("p", "quote", it.quote));
    var row = el("div", "row");
    if (kind === "new" || kind === "due") {
      if (future) row.appendChild(btn("오늘", "", function () { setItem(it, { status: "todo", plan_date: state.today }); }));
      row.appendChild(btn("나중", "", function () { setItem(it, { status: "later" }); }));
      row.appendChild(btn("안 함", "", function () { setItem(it, { status: "skipped" }); }));
    } else if (kind === "todo") {
      row.appendChild(btn("나중으로", "", function () { setItem(it, { status: "later" }); }));
    } else if (kind === "later" && future) {
      row.appendChild(btn(shortDate(it.due_date) + "에 하기", "", function () { setItem(it, { status: "todo", plan_date: it.due_date }); }));
    }
    var edit = editForm(it), cal = (kind === "todo" || kind === "later") ? calendarRow(it) : null;
    row.appendChild(btn("고치기", "", function () { edit.hidden = !edit.hidden; if (cal) cal.hidden = true; }));
    if (cal) row.appendChild(btn("캘린더", "", function () { cal.hidden = !cal.hidden; edit.hidden = true; }));
    if (kind !== "new" && kind !== "due") row.appendChild(btn("지우기", "ghost", function () { delItem(it); }));
    more.appendChild(row); more.appendChild(edit); if (cal) more.appendChild(cal);
    li.appendChild(more);
    return li;
  }
  function fill(listId, countId, arr, kind, empty) {
    var ul = $(listId); ul.textContent = "";
    if (countId) $(countId).textContent = String(arr.length);
    if (!arr.length && empty) { var li = el("li"); li.appendChild(el("p", "empty", empty)); ul.appendChild(li); }
    arr.forEach(function (it) { ul.appendChild(itemNode(it, kind)); });
  }

  /* ---------- 오늘(날짜별) 화면 ---------- */
  function renderWeek(days) {
    var ol = $("week"); ol.textContent = "";
    days.forEach(function (d) {
      var dt = toDate(d.date), li = el("li");
      var b = btn("", (d.date === state.date ? "sel " : "") + (d.date === state.today ? "today" : ""), function () { state.date = d.date; refresh(); });
      b.setAttribute("aria-label", nice(d.date) + ", 남은 일 " + d.left + "건, 끝낸 일 " + d.done + "건");
      if (d.date === state.date) b.setAttribute("aria-current", "date");
      b.appendChild(el("span", "wd", DAYS[dt.getDay()]));
      b.appendChild(el("span", "dn", String(dt.getDate())));
      var dots = el("span", "dots");
      if (d.left) dots.appendChild(el("b", "", String(d.left)));
      if (d.left && d.done) dots.appendChild(document.createTextNode(" · "));
      if (d.done) dots.appendChild(document.createTextNode("✓" + d.done));
      b.appendChild(dots); li.appendChild(b); ol.appendChild(li);
    });
  }
  function renderNeedMe(list) {
    var box = $("need-me"); box.textContent = "";
    list.forEach(function (inp) {
      var n = el("div", "notice");
      n.appendChild(el("strong", "", "\"" + (inp.title || KIND[inp.kind]) + "\"에서 누가 나인가요?"));
      n.appendChild(el("span", "msg", "알려 주면 내 일만 다시 골라 드려요."));
      var row = el("div", "row");
      inp.speakers.forEach(function (s) {
        row.appendChild(btn(s, "", function () {
          api("/api/inputs/" + inp.id, { method: "PATCH", json: { me_speaker: s } }).then(refresh).catch(fail("in-msg"));
        }));
      });
      n.appendChild(row); box.appendChild(n);
    });
  }
  function renderBriefs(list) {
    /* 회의·통화 요약: 한 줄로 접혀 있고, 누르면 전체가 펼쳐진다 */
    var ul = $("l-brief"); ul.textContent = "";
    $("s-brief").hidden = !list.length; $("c-brief").textContent = String(list.length);
    list.forEach(function (b) {
      var li = el("li", "item brief"), head = el("div", "head"), more = el("div", "more"); more.hidden = true;
      var what = btn("", "what", function () { more.hidden = !more.hidden; what.setAttribute("aria-expanded", String(!more.hidden)); });
      what.setAttribute("aria-expanded", "false");
      what.appendChild(el("span", "txt", b.title || KIND[b.kind]));
      what.appendChild(el("span", "msg clip one", b.summary));
      head.appendChild(what); li.appendChild(head);
      more.appendChild(el("p", "summary", b.summary));
      var row = el("div", "row");
      row.appendChild(btn("넣은 것에서 보기", "", function () { document.querySelector('.tabs button[data-tab="inputs"]').click(); openInput(b.id); }));
      more.appendChild(row); li.appendChild(more); ul.appendChild(li);
    });
  }
  function renderDay(d) {
    state.today = d.today;
    var isToday = d.is_today, past = d.date < d.today;
    $("d-label").textContent = nice(d.date);
    $("d-today").hidden = isToday;
    $("btn-add").hidden = past; $("s-new").hidden = !isToday || (!d["new"].length && !d.pending_inputs);
    $("capture").hidden = !isToday; $("add-on").textContent = isToday ? "오늘 할 일로 들어가요." : nice(d.date) + " 할 일로 들어가요.";
    $("t-todo").textContent = isToday ? "오늘" : past ? "못 끝낸 일" : "하기로 한 일";
    fill("l-new", "c-new", d["new"], "new", "");
    fill("l-todo", "c-todo", d.todo, "todo", isToday ? "아직 없어요. 오른쪽 아래 + 를 눌러 말하거나 녹음을 넣어 보세요." : past ? "이날 남긴 일이 없어요." : "이날 하기로 한 일이 아직 없어요.");
    $("s-due").hidden = !d.due.length; fill("l-due", "c-due", d.due, "due");
    $("s-done").hidden = !d.done.length; fill("l-done", "c-done", d.done, "done");
    $("sum-text").textContent = d.summary || (isToday ? "하루를 마칠 때 누르면 한 일과 남은 일을 정리해 드려요." : past ? "이날의 정리가 없어요." : "");
    $("btn-sum").hidden = d.date > d.today;
    $("btn-sum").textContent = d.summary ? "다시 정리해 줘" : "정리해 줘";
    renderNeedMe(d.need_me || []);
    renderBriefs(d.briefs || []);
    $("pending").hidden = !d.pending_inputs;
    $("bulk").hidden = !(isToday && d["new"].length > 1);
    clearTimeout(state.poll);
    if (d.pending_inputs && state.tab === "today") state.poll = setTimeout(refresh, 2500);
  }
  function refresh() {
    if (state.tab === "later") return api("/api/items?status=later").then(function (a) { fill("l-later", "c-later", a, "later", "나중으로 미룬 일이 여기에 있어요."); }).catch(fail("in-msg"));
    if (state.tab === "inputs") return loadInputs();
    return Promise.all([api("/api/day?date=" + state.date), api("/api/week?date=" + state.date)])
      .then(function (r) { renderDay(r[0]); renderWeek(r[1]); }).catch(fail("in-msg"));
  }
  $("btn-bulk").addEventListener("click", function () {
    api("/api/items/accept-all", { method: "POST", json: {} }).then(function (r) { say("in-msg", r.moved + "건을 넣었어요."); refresh(); }).catch(fail("in-msg"));
  });
  $("d-prev").addEventListener("click", function () { state.date = shift(state.date, -1); refresh(); });
  $("d-next").addEventListener("click", function () { state.date = shift(state.date, 1); refresh(); });
  $("d-today").addEventListener("click", function () { state.date = state.today; refresh(); });
  $("add-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var t = $("add-text").value.trim(); if (!t) return;
    api("/api/items", { method: "POST", json: { text: t, plan_date: state.date } }).then(function () { $("add-text").value = ""; sheet(false); refresh(); }).catch(fail("in-msg"));
  });
  $("btn-sum").addEventListener("click", function () {
    $("btn-sum").disabled = true; $("sum-text").textContent = "정리하고 있어요…";
    api("/api/day/close?date=" + state.date, { method: "POST" }).then(function (r) { $("sum-text").textContent = r.summary || r.note || ""; })
      .catch(function (e) { $("sum-text").textContent = e.message; })
      .then(function () { $("btn-sum").disabled = false; $("btn-sum").textContent = "다시 정리해 줘"; });
  });

  var mic = { on: false, rec: null, text: "", media: null, chunks: [] };

  /* ---------- 넣기 창 ---------- */
  function sheet(open) {
    $("sheet").hidden = !open; $("btn-add").setAttribute("aria-expanded", String(open));
    if (!open && mic.on) { if (mic.rec) mic.rec.stop(); else if (mic.media) mic.media.stop(); }
  }
  $("btn-add").addEventListener("click", function () { sheet(true); });
  $("sheet-close").addEventListener("click", function () { sheet(false); });
  $("sheet-back").addEventListener("click", function () { sheet(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("sheet").hidden) sheet(false); });

  /* ---------- 넣기: 글, 파일, 말하기 ---------- */
  function send(form, okText) {
    form.append("on", state.today);
    say("in-msg", "보내고 있어요…");
    return api("/api/inputs", { method: "POST", form: form }).then(function () { say("in-msg", okText); sheet(false); refresh(); }).catch(fail("in-msg"));
  }
  $("btn-paste").addEventListener("click", function () { var f = $("paste-form"); f.hidden = !f.hidden; if (!f.hidden) $("paste-text").focus(); });
  $("paste-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var fd = new FormData(); fd.append("kind", $("paste-kind").value); fd.append("text", $("paste-text").value);
    send(fd, "받았어요. 챙길 것을 찾고 있어요.").then(function () { $("paste-text").value = ""; $("paste-form").hidden = true; });
  });
  function sendFiles(ev) {
    var files = Array.prototype.slice.call(ev.target.files || []);
    files.reduce(function (p, f) {
      return p.then(function () { var fd = new FormData(); fd.append("kind", "file"); fd.append("file", f, f.name); return send(fd, f.name + " 받았어요. 챙길 것을 찾고 있어요."); });
    }, Promise.resolve());
    ev.target.value = "";
  }
  $("file").addEventListener("change", sendFiles);
  $("photo").addEventListener("change", sendFiles);

  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  function micDone(text) {
    mic.on = false; $("btn-mic").classList.remove("rec"); $("btn-mic").textContent = "말하기";
    if (!text.trim()) { say("mic-msg", "들린 말이 없었어요. 다시 눌러 말해 주세요."); return; }
    say("mic-msg", "누르고 할 일을 말해 주세요.");
    var fd = new FormData(); fd.append("kind", "memo"); fd.append("title", "말로 한 메모"); fd.append("text", text);
    send(fd, "들었어요. 적어 두는 중이에요.");
  }
  function micStartSpeech() {
    var r = new SR(); r.lang = "ko-KR"; r.continuous = true; r.interimResults = true; mic.text = ""; mic.rec = r;
    r.onresult = function (e) {
      var live = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) mic.text += e.results[i][0].transcript + " "; else live += e.results[i][0].transcript;
      }
      say("mic-msg", (mic.text + live).trim() || "듣고 있어요…");
    };
    r.onerror = function (e) { if (e.error === "not-allowed") say("mic-msg", "마이크를 쓸 수 있게 허용해 주세요.", true); };
    r.onend = function () { if (mic.on) micDone(mic.text); };
    r.start();
  }
  function micStartRecord() {
    return navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      mic.chunks = []; mic.media = new MediaRecorder(stream);
      mic.media.ondataavailable = function (e) { if (e.data.size) mic.chunks.push(e.data); };
      mic.media.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        mic.on = false; $("btn-mic").classList.remove("rec"); $("btn-mic").textContent = "말하기"; say("mic-msg", "누르고 할 일을 말해 주세요.");
        var fd = new FormData(); fd.append("kind", "memo"); fd.append("title", "말로 한 메모");
        fd.append("file", new Blob(mic.chunks, { type: mic.media.mimeType || "audio/webm" }), "memo.webm");
        send(fd, "들었어요. 글로 바꾸는 중이에요.");
      };
      mic.media.start();
    });
  }
  $("btn-mic").addEventListener("click", function () {
    if (mic.on) { if (mic.rec) mic.rec.stop(); else if (mic.media) mic.media.stop(); return; }
    if (!window.isSecureContext) {
      say("mic-msg", "말하기는 https 주소로 열었을 때만 돼요. 지금 주소에서는 글 붙여넣기나 사진을 써 주세요.", true); return;
    }
    mic.on = true; mic.rec = null; mic.media = null;
    $("btn-mic").classList.add("rec"); $("btn-mic").textContent = "다 말했어요"; say("mic-msg", "듣고 있어요…");
    try {
      if (SR) micStartSpeech();
      else if (navigator.mediaDevices && window.MediaRecorder && state.me && state.me.stt) micStartRecord().catch(function () { mic.on = false; $("btn-mic").classList.remove("rec"); $("btn-mic").textContent = "말하기"; say("mic-msg", "마이크를 쓸 수 있게 허용해 주세요.", true); });
      else { mic.on = false; $("btn-mic").classList.remove("rec"); $("btn-mic").textContent = "말하기"; say("mic-msg", "이 브라우저에서는 말하기를 쓸 수 없어요. 글 붙여넣기를 써 주세요.", true); }
    } catch (e) { mic.on = false; $("btn-mic").classList.remove("rec"); $("btn-mic").textContent = "말하기"; say("mic-msg", "마이크를 켜지 못했어요.", true); }
  });

  /* ---------- 넣은 것 ---------- */
  function loadInputs() {
    $("input-detail").hidden = true; $("inputs-list").hidden = false;
    return api("/api/inputs").then(function (list) {
      var ul = $("l-inputs"); ul.textContent = "";
      if (!list.length) { var e = el("li"); e.appendChild(el("p", "empty", "보낸 녹음이 여기에 날짜별로 쌓여요.")); ul.appendChild(e); }
      var lastDate = "", busy = false;
      list.forEach(function (inp) {
        if (inp.received_date !== lastDate) { lastDate = inp.received_date; var h = el("li"); h.appendChild(el("p", "empty", nice(lastDate))); ul.appendChild(h); }
        if (inp.status !== "extracted" && inp.status !== "failed") busy = true;
        var li = el("li", "item");
        var head = el("div", "head"); head.appendChild(el("span", "what", inp.title || KIND[inp.kind])); li.appendChild(head);
        var m = el("div", "meta");
        m.appendChild(el("span", "tag", KIND[inp.kind]));
        m.appendChild(el("span", "tag" + (inp.status === "failed" ? " carry" : ""), STATUS[inp.status] || inp.status));
        if (inp.status === "extracted") m.appendChild(el("span", "tag", "챙길 것 " + inp.item_count + "건"));
        li.appendChild(m);
        if (inp.error) li.appendChild(el("p", "msg err", inp.error));
        if (inp.summary) li.appendChild(el("p", "msg clip", inp.summary));
        var row = el("div", "row"); row.appendChild(btn("열어 보기", "", function () { openInput(inp.id); })); li.appendChild(row);
        ul.appendChild(li);
      });
      clearTimeout(state.poll);
      if (busy && state.tab === "inputs") state.poll = setTimeout(refresh, 2500);
    }).catch(fail("in-msg"));
  }
  function openInput(id) {
    api("/api/inputs/" + id).then(function (inp) {
      var box = $("input-detail"); box.textContent = ""; box.hidden = false; $("inputs-list").hidden = true;
      box.appendChild(btn("‹ 목록으로", "link", loadInputs));
      box.appendChild(el("h2", "", inp.title || KIND[inp.kind]));
      var m = el("div", "meta"); m.appendChild(el("span", "tag", KIND[inp.kind])); m.appendChild(el("span", "tag", nice(inp.received_date))); m.appendChild(el("span", "tag", STATUS[inp.status] || inp.status)); box.appendChild(m);
      if (inp.error) box.appendChild(el("p", "msg err", inp.error));
      if (inp.speakers.length) {
        var n = el("div", "notice"); n.appendChild(el("strong", "", "누가 나인가요?"));
        var row = el("div", "row");
        inp.speakers.forEach(function (s) {
          row.appendChild(btn(s, inp.me_speaker === s ? "on" : "", function () {
            api("/api/inputs/" + id, { method: "PATCH", json: { me_speaker: s } }).then(function () { openInput(id); });
          }));
        });
        n.appendChild(row); box.appendChild(n);
      }
      if (inp.summary) { box.appendChild(el("h2", "", "요약")); box.appendChild(el("p", "summary", inp.summary)); }
      var mine = inp.items.filter(function (it) { return it.status !== "other"; });
      var others = inp.items.filter(function (it) { return it.status === "other"; });
      var LABEL = { "new": "고르기 전", todo: "하기로 함", later: "나중", skipped: "안 함", done: "끝냄" };
      box.appendChild(el("h2", "", "여기서 나온 내 일"));
      var ul = el("ul", "list");
      if (!mine.length) { var e = el("li"); e.appendChild(el("p", "empty", "챙길 것이 없었어요.")); ul.appendChild(e); }
      mine.forEach(function (it) {
        var li = el("li", "item" + (it.status === "done" ? " done" : ""));
        var head = el("div", "head"); head.appendChild(el("span", "what", it.text)); li.appendChild(head);
        var m = meta(it, "detail"); m.appendChild(el("span", "tag", LABEL[it.status] || it.status)); li.appendChild(m);
        if (it.quote) li.appendChild(el("p", "quote", it.quote));
        if (it.status === "skipped") {
          var r1 = el("div", "row"); r1.appendChild(btn("다시 내 일로", "", function () { api("/api/items/" + it.id, { method: "PATCH", json: { status: "todo", plan_date: state.today } }).then(function () { openInput(id); }); })); li.appendChild(r1);
        }
        ul.appendChild(li);
      });
      box.appendChild(ul);
      if (others.length) {
        box.appendChild(el("h2", "", "다른 사람 일로 본 것"));
        box.appendChild(el("p", "msg", "내 일이면 가져오세요. 오늘 할 일로 들어가요."));
        var ol = el("ul", "list");
        others.forEach(function (it) {
          var li = el("li", "item");
          var head = el("div", "head"); head.appendChild(el("span", "what", it.text)); li.appendChild(head);
          li.appendChild(meta(it, "detail"));
          var r2 = el("div", "row");
          r2.appendChild(btn("내 일로 가져오기", "pick", function () {
            api("/api/items/" + it.id, { method: "PATCH", json: { status: "todo", plan_date: it.due_date && it.due_date > state.today ? it.due_date : state.today } }).then(function () { openInput(id); }).catch(fail("in-msg"));
          }));
          li.appendChild(r2); ol.appendChild(li);
        });
        box.appendChild(ol);
      }
      box.appendChild(el("h2", "", "글 내용"));
      box.appendChild(el("pre", "transcript", inp.transcript || "(아직 글이 없어요)"));
      var act = el("div", "row");
      act.appendChild(btn("다시 뽑기", "", function () { api("/api/inputs/" + id, { method: "PATCH", json: { reextract: true } }).then(function () { setTimeout(function () { openInput(id); }, 1500); }); }));
      var del = btn("이 녹음 지우기", "danger", function () {
        if (del.dataset.sure) { api("/api/inputs/" + id, { method: "DELETE" }).then(loadInputs); return; }
        del.dataset.sure = "1"; del.textContent = "한 번 더 누르면 지워요";
      });
      act.appendChild(del); box.appendChild(act);
      box.appendChild(el("p", "msg", "녹음을 지워도 이미 고른 일은 남아요."));
    }).catch(fail("in-msg"));
  }

  /* ---------- 휴대폰 연결 (QR) ---------- */
  function showLink(kind) {
    api("/api/link", { method: "POST", json: { kind: kind } }).then(function (r) {
      var box = $("link-qr"); box.hidden = false;
      box.innerHTML = r.svg;                       /* 서버가 만든 QR 그림 */
      var svg = box.querySelector("svg"); if (svg) { svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "연결용 QR"); }
      say("link-msg", (kind === "family" ? "가족이 찍으면 이름만 정하고 들어와요. " : "내 휴대폰으로 찍으면 같은 목록으로 바로 들어와요. ") + r.minutes + "분 동안 쓸 수 있어요.");
      $("link-url").textContent = r.secure ? r.url : r.url + "\n이 주소는 집 와이파이에서만 열리고, 말하기와 홈 화면 설치는 안 돼요. Tailscale을 켜면 집 밖 주소로 바뀌어요.";
    }).catch(fail("link-msg"));
  }
  $("btn-link").addEventListener("click", function () { var b = $("link-box"); b.hidden = !b.hidden; if (!b.hidden) b.scrollIntoView({ block: "nearest" }); });
  $("link-me").addEventListener("click", function () { showLink("me"); });
  $("link-family").addEventListener("click", function () { showLink("family"); });

  /* ---------- 캘린더 연결 ---------- */
  var PROVIDER = { naver: "네이버 캘린더", google: "구글 캘린더" };
  function renderCal(c) {
    var linked = !!c.provider;
    $("cal-linked").hidden = !linked; $("cal-choose").hidden = linked;
    $("cal-state").textContent = linked
      ? PROVIDER[c.provider] + (c.label && c.label !== PROVIDER[c.provider] ? " · " + c.label : "") + "에 연결돼 있어요. 날짜를 정한 일이 자동으로 들어가요."
      : "연결하면 날짜를 정한 일이 캘린더에 자동으로 들어가요. 하나만 골라 연결해 주세요.";
    $("cal-err").textContent = c.status || "";
    $("cal-mode").value = c.mode || "timed";
    $("google-go").hidden = !c.google_ready;
    $("google-hint").textContent = c.google_ready
      ? "구글 로그인 화면으로 이동해요. 캘린더 일정을 넣고 고치는 권한만 요청해요."
      : "이 PC에서 구글 연결 준비(한 번)가 아직 안 됐어요. INSTALL.md의 '구글 캘린더 연결 준비'를 따라 한 뒤 서버를 다시 켜 주세요.";
  }
  function loadCal() { return api("/api/calendar").then(renderCal).catch(function (e) { $("cal-err").textContent = e.message; }); }
  $("btn-cal").addEventListener("click", function () {
    var box = $("cal-box"); box.hidden = !box.hidden;
    if (!box.hidden) { loadCal(); box.scrollIntoView({ block: "nearest" }); }
  });
  $("naver-form").addEventListener("submit", function (ev) {
    ev.preventDefault(); $("cal-err").textContent = "";
    api("/api/calendar/naver", { method: "POST", json: { user: $("naver-id").value, password: $("naver-pw").value } })
      .then(function (c) { $("naver-pw").value = ""; renderCal(c); }).catch(function (e) { $("cal-err").textContent = e.message; });
  });
  $("cal-mode").addEventListener("change", function () {
    api("/api/calendar/mode", { method: "POST", json: { mode: $("cal-mode").value } }).then(renderCal).catch(function (e) { $("cal-err").textContent = e.message; });
  });
  $("cal-unlink").addEventListener("click", function () {
    api("/api/calendar", { method: "DELETE" }).then(renderCal).catch(function (e) { $("cal-err").textContent = e.message; });
  });

  /* ---------- 탭 ---------- */
  Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (b) {
    b.addEventListener("click", function () {
      state.tab = b.dataset.tab; clearTimeout(state.poll);
      Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (x) { x.classList.toggle("on", x === b); });
      $("tab-today").hidden = state.tab !== "today"; $("tab-later").hidden = state.tab !== "later"; $("tab-inputs").hidden = state.tab !== "inputs";
      document.querySelector(".top").hidden = state.tab !== "today"; $("week").hidden = state.tab !== "today";
      if (state.tab !== "today") $("btn-add").hidden = true;
      refresh();
    });
  });
  document.addEventListener("visibilitychange", function () { if (!document.hidden && state.me) refresh(); });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});
  boot();
})();
