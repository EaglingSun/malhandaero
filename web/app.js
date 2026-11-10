/* 말한대로 화면. 빌드 단계 없이 그대로 도는 한 파일. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var DAYS = ["일", "월", "화", "수", "목", "금", "토"];
  var KIND = { call: "통화", meeting: "회의", memo: "내 메모", file: "파일", photo: "사진" };
  var STATUS = { received: "받았어요", transcribing: "듣고 글로 옮기는 중", ready: "준비됨", extracting: "듣고 정리하는 중", extracted: "다 적어 뒀어요", failed: "못 했어요" };
  function pendingText(list) {
    /* 처리 중 안내. 앱 말투로 가볍게, 긴 회의는 시간이 걸린다고 미리 말한다 */
    var longs = list.filter(function (x) { return x.long || x.kind === "meeting"; });
    var name = function (x) { return x.title ? "\"" + x.title.replace(/\.[a-z0-9]+$/i, "") + "\"" : KIND[x.kind] || "이야기"; };
    if (longs.length) return name(longs[0]) + (list.length > 1 ? " 외 " + (list.length - 1) + "건" : "") + "을 꼼꼼히 듣고 정리하는 중이에요 ☕ 긴 회의는 몇 분 걸려요. 다른 일 보고 오셔도 돼요.";
    if (list.some(function (x) { return x.status === "transcribing"; })) return "녹음을 듣고 글로 옮기는 중이에요. 길이만큼 시간이 걸려요.";
    return (list.length > 1 ? list.length + "건을 " : "") + "듣고 챙길 것을 적어 두는 중이에요. 보통 10~30초면 돼요.";
  }
  var state = { me: null, date: null, today: null, tab: "today", poll: null, open: {}, detail: null, ym: null };
  /* 펼친 카드를 기억한다. 처리 중에는 화면이 몇 초마다 다시 그려지는데, 그때 펼친 것이 닫히지 않게 */
  function toggleOpen(key, more, what) {
    more.hidden = !more.hidden; what.setAttribute("aria-expanded", String(!more.hidden));
    if (more.hidden) delete state.open[key]; else state.open[key] = true;
  }
  function restoreOpen(key, more, what) {
    if (state.open[key]) { more.hidden = false; what.setAttribute("aria-expanded", "true"); return true; }
    return false;
  }

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
      $("ver").textContent = me.version ? "버전 " + me.version : "";
      var q = new URLSearchParams(location.search).get("shared");
      if (q) { say("in-msg", q === "0" ? "받을 내용이 없었어요." : q + "건 받았어요. 듣고 적어 둘게요."); history.replaceState(null, "", "/"); }
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
    if (it.cal_ref) m.appendChild(el("span", "tag synced", it.addon === "calendar" ? "캘린더에서" : "캘린더"));
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
    var okey = "item:" + it.id;
    var what = btn("", "what", function () { toggleOpen(okey, more, what); });
    what.setAttribute("aria-expanded", "false"); restoreOpen(okey, more, what);
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

    if (it.details && it.details.length) { var dl = el("ul", "details"); it.details.forEach(function (d) { dl.appendChild(el("li", "", d)); }); more.appendChild(dl); }
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
  function bullets(text) {
    /* 요약을 목록으로. 새 버전은 '- ' 줄로 오고, 예전 줄글은 문장 단위로 나눈다 */
    var lines = (text || "").split(/\n+/).map(function (l) { return l.replace(/^\s*[-•·*]\s*/, "").trim(); }).filter(Boolean);
    if (lines.length <= 1) lines = (text || "").split(/(?<=[.!?。])\s+/).map(function (l) { return l.trim(); }).filter(Boolean);
    var ul = el("ul", "bullets");
    lines.forEach(function (l) { ul.appendChild(el("li", "", l)); });
    return ul;
  }
  function renderBriefs(list) {
    /* 들은 이야기: 제목만 한 줄씩. 누르면 요약 목록이 펼쳐진다 */
    var ul = $("l-brief"); ul.textContent = "";
    $("s-brief").hidden = !list.length; $("c-brief").textContent = String(list.length);
    list.forEach(function (b) {
      var li = el("li", "item brief"), head = el("div", "head"), more = el("div", "more"); more.hidden = true;
      var okey = "brief:" + b.id, loaded = false, box = el("div");
      function loadMinutes() {
        if (loaded || more.hidden) return; loaded = true;
        api("/api/inputs/" + b.id).then(function (inp) { box.appendChild(minutesView(inp)); }).catch(function () {});
      }
      var what = btn("", "what", function () { toggleOpen(okey, more, what); loadMinutes(); });
      what.setAttribute("aria-expanded", "false");
      what.appendChild(el("span", "txt", b.title || KIND[b.kind]));
      var m = el("div", "meta"); m.appendChild(el("span", "tag", KIND[b.kind] || b.kind)); what.appendChild(m);
      head.appendChild(what); li.appendChild(head);
      if (b.summary) more.appendChild(bullets(b.summary));
      more.appendChild(box);
      if (restoreOpen(okey, more, what)) loadMinutes();
      var row = el("div", "row");
      row.appendChild(btn("넣은 것에서 보기", "", function () { document.querySelector('.tabs button[data-tab="inputs"]').click(); openInput(b.id); }));
      more.appendChild(row); li.appendChild(more); ul.appendChild(li);
    });
  }
  function minutesView(inp) {
    /* 회의록: 주제별 논의·결정, 확인할 것, 내 일·맡긴 일. 복사하거나 파일로 받을 수 있다 */
    var wrap = el("div", "minutes"), m = inp.minutes || {};
    if (m.attendees && m.attendees.length) wrap.appendChild(el("p", "msg", "참석: " + m.attendees.join(", ")));
    (m.topics || []).forEach(function (t) {
      var sec = el("div", "topic"); sec.appendChild(el("strong", "", t.topic));
      var ul = el("ul", "bullets plain"); (t.points || []).forEach(function (x) { ul.appendChild(el("li", "", x)); }); if (t.points && t.points.length) sec.appendChild(ul);
      if (t.decisions && t.decisions.length) { var d = el("ul", "bullets decided"); t.decisions.forEach(function (x) { d.appendChild(el("li", "", x)); }); sec.appendChild(d); }
      wrap.appendChild(sec);
    });
    if (m.questions && m.questions.length) { var q = el("div", "topic"); q.appendChild(el("strong", "", "확인할 것")); var ql = el("ul", "bullets plain"); m.questions.forEach(function (x) { ql.appendChild(el("li", "", x)); }); q.appendChild(ql); wrap.appendChild(q); }
    if (m.next && m.next.length) { var nx = el("div", "topic"); nx.appendChild(el("strong", "", "다음 일정")); var nl = el("ul", "bullets plain"); m.next.forEach(function (x) { nl.appendChild(el("li", "", x)); }); nx.appendChild(nl); wrap.appendChild(nx); }
    var others = (inp.items || []).filter(function (i) { return i.status === "other"; });
    if (others.length) { var o = el("div", "topic"); o.appendChild(el("strong", "", "맡긴 일")); var ol = el("ul", "bullets plain"); others.forEach(function (i) { ol.appendChild(el("li", "", i.text + (i.who ? " · " + i.who : "") + (i.due_text ? " · " + i.due_text : ""))); }); o.appendChild(ol); wrap.appendChild(o); }
    if (inp.has_minutes || others.length) {
      var row = el("div", "row"), msg = el("span", "msg");
      row.appendChild(btn("회의록 복사", "", function () {
        fetch("/api/inputs/" + inp.id + "/minutes.md", { credentials: "same-origin" }).then(function (r) { return r.text(); }).then(function (t) {
          return navigator.clipboard.writeText(t);
        }).then(function () { msg.textContent = "복사했어요. 메모 앱이나 회의록에 붙여 넣으세요."; }).catch(function () { msg.textContent = "복사하지 못했어요. '파일로 받기'를 써 주세요."; });
      }));
      var a = el("a", "filebtn", "파일로 받기"); a.href = "/api/inputs/" + inp.id + "/minutes.md"; row.appendChild(a);
      wrap.appendChild(row); wrap.appendChild(msg);
    }
    return wrap;
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
    $("sum-text").textContent = d.summary || (isToday ? "오늘 할 일을 마쳤으면 누르세요. 한 일과 남은 일을 정리해 둘게요. 남은 일은 내일로 넘어가요." : past ? "이날의 마무리가 없어요." : "");
    $("btn-sum").hidden = d.date > d.today;
    var diaryOn = !!(state.me && state.me.diary);
    $("diary").hidden = !diaryOn || d.date > d.today;
    $("btn-diary").textContent = diaryOn ? "한 줄 끄기" : "오늘 한 줄도 남길래요";
    if (diaryOn) {
      $("note").value = d.note || "";
      state.mood = d.mood || "";
      paintMood();
      say("note-msg", "");
    }
    $("btn-sum").textContent = d.summary ? "마무리 다시 쓰기" : "오늘은 여기까지";
    renderNeedMe(d.need_me || []);
    renderBriefs(d.briefs || []);
    $("pending").hidden = !d.pending_inputs; if (d.pending_inputs) $("pending").textContent = pendingText(d.pending || []);
    $("bulk").hidden = !(isToday && d["new"].length > 1);
    clearTimeout(state.poll);
    if (d.pending_inputs && state.tab === "today") state.poll = setTimeout(function () { refresh(true); }, 2500);
  }
  function renderCalEvents(r) {
    /* 연결된 캘린더의 그날 일정. '할 일로'를 누르면 같은 일정을 가리키는 할 일이 된다 */
    var sec = $("s-cal-ev"), ul = $("l-cal-ev"); ul.textContent = "";
    if (!r || !r.linked || (!r.events.length && !r.error && !r.hidden)) { sec.hidden = true; return; }
    sec.hidden = false; $("c-cal-ev").textContent = String(r.events.length); say("cal-ev-msg", r.error || "", !!r.error);
    r.events.forEach(function (e) {
      var li = el("li", "item ev"), head = el("div", "head"), what = el("div", "what");
      what.appendChild(el("span", "txt", e.title));
      var m = el("div", "meta"); if (e.time) m.appendChild(el("span", "tag when", niceTime(e.time))); else m.appendChild(el("span", "tag", "하루 종일"));
      what.appendChild(m); head.appendChild(what);
      if (e.item_id) head.appendChild(el("span", "tag", "할 일로 들어옴"));
      else head.appendChild(btn("할 일로", "quick", function () {
        api("/api/calendar/events/import", { method: "POST", json: { ref: e.ref, title: e.title, time: e.time, date: state.date } }).then(refresh).catch(fail("in-msg"));
      }));
      head.appendChild(btn("숨기기", "ghost", function () { api("/api/calendar/events/hide", { method: "POST", json: { ref: e.ref } }).then(refresh).catch(fail("in-msg")); }));
      li.appendChild(head); ul.appendChild(li);
    });
    if (r.hidden) {
      var n = $("cal-ev-msg"); n.className = "msg"; n.textContent = "숨긴 일정 " + r.hidden + "건 ";
      n.appendChild(btn("다시 보기", "link", function () { api("/api/calendar/events/unhide", { method: "POST", json: {} }).then(refresh).catch(fail("in-msg")); }));
    }
  }
  function refresh(fromPoll) {
    if (state.tab === "later") return api("/api/items?status=later").then(function (a) { fill("l-later", "c-later", a, "later", "나중으로 미룬 일이 여기에 있어요."); }).catch(fail("in-msg"));
    if (state.tab === "inputs") return state.detail ? openInput(state.detail) : loadInputs();
    if (state.tab === "month") return loadMonth();
    var pending = Promise.all([api("/api/day?date=" + state.date), api("/api/week?date=" + state.date)])
      .then(function (r) { renderDay(r[0]); renderWeek(r[1]); }).catch(fail("in-msg"));
    if (fromPoll !== true) api("/api/calendar/events?date=" + state.date).then(renderCalEvents).catch(function () {});  // 처리 중 자동 새로고침 때는 캘린더를 두드리지 않는다
    return pending;
  }
  $("btn-skip-all").addEventListener("click", function () {
    /* 한 번에 실행하고 되돌리기 버튼을 준다 */
    api("/api/items/skip-all", { method: "POST", json: {} }).then(function (r) {
      var n = $("in-msg"); n.className = "msg"; n.textContent = r.skipped + "건을 안 함으로 넘겼어요. ";
      if (r.ids && r.ids.length) {
        n.appendChild(btn("되돌리기", "link", function () {
          api("/api/items/restore", { method: "POST", json: { ids: r.ids } }).then(function (x) { say("in-msg", x.restored + "건을 되돌렸어요."); refresh(); }).catch(fail("in-msg"));
        }));
      }
      refresh();
    }).catch(fail("in-msg"));
  });
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
  $("btn-diary").addEventListener("click", function () {
    var on = !(state.me && state.me.diary);
    api("/api/settings/diary", { method: "POST", json: { enabled: on } }).then(function () { state.me.diary = on; refresh(); if (on) setTimeout(function () { $("note").focus(); }, 50); }).catch(fail("in-msg"));
  });
  function paintMood() {
    Array.prototype.forEach.call(document.querySelectorAll("#moods button"), function (b) { b.classList.toggle("on", b.dataset.mood === state.mood); b.setAttribute("aria-checked", b.dataset.mood === state.mood ? "true" : "false"); });
  }
  function saveNote() {
    var v = $("note").value.trim();
    api("/api/day/note?date=" + state.date, { method: "POST", json: { note: v, mood: state.mood || "" } })
      .then(function () { say("note-msg", (v || state.mood) ? "남겨 뒀어요." : ""); })
      .catch(function (e) { say("note-msg", e.message, true); });
  }
  $("moods").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-mood]"); if (!b) return;
    state.mood = state.mood === b.dataset.mood ? "" : b.dataset.mood;   // 다시 누르면 해제
    paintMood(); saveNote();
  });
  $("note-chips").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    var cur = $("note").value.trim();
    $("note").value = cur ? (cur.indexOf(b.textContent) >= 0 ? cur : cur + ", " + b.textContent) : b.textContent;
    saveNote();
  });
  $("note").addEventListener("change", saveNote);
  $("note").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); $("note").blur(); } });
  $("btn-sum").addEventListener("click", function () {
    $("btn-sum").disabled = true; $("sum-text").textContent = "오늘 하루를 정리하고 있어요…";
    api("/api/day/close?date=" + state.date, { method: "POST" }).then(function (r) { $("sum-text").textContent = r.summary || r.note || ""; })
      .catch(function (e) { $("sum-text").textContent = e.message; })
      .then(function () { $("btn-sum").disabled = false; $("btn-sum").textContent = "마무리 다시 쓰기"; });
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
    send(fd, "받았어요. 듣고 적어 둘게요.").then(function () { $("paste-text").value = ""; $("paste-form").hidden = true; });
  });
  function sendFiles(ev) {
    var files = Array.prototype.slice.call(ev.target.files || []);
    files.reduce(function (p, f) {
      return p.then(function () { var fd = new FormData(); fd.append("kind", "file"); fd.append("file", f, f.name); return send(fd, f.name + " 받았어요. 듣고 적어 둘게요."); });
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
    state.detail = null;
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
        if (inp.summary) li.appendChild(el("p", "msg clip", inp.summary.replace(/\n+/g, " ")));
        var row = el("div", "row"); row.appendChild(btn("열어 보기", "", function () { openInput(inp.id); })); li.appendChild(row);
        ul.appendChild(li);
      });
      clearTimeout(state.poll);
      if (busy && state.tab === "inputs") state.poll = setTimeout(function () { refresh(true); }, 2500);
      api("/api/stats?days=30").then(function (st) {
        if (!st.inputs.total) { $("stats").textContent = ""; return; }
        var m = st.seconds_to_list.median, parts = ["지난 30일 · 넣은 것 " + st.inputs.total + "건"];
        if (m != null) parts.push("넣고 " + (m < 90 ? Math.round(m) + "초" : Math.round(m / 60) + "분") + "이면 목록에");
        parts.push("뽑힌 내 일 " + st.items.extracted_mine + "건" + (st.items.skip_ratio != null ? " (안 함 " + Math.round(st.items.skip_ratio * 100) + "%)" : ""));
        if (st.items.delegated) parts.push("맡긴 일 " + st.items.delegated);
        if (st.items.manual) parts.push("직접 적음 " + st.items.manual);
        if (st.items.per_meeting != null) parts.push("회의당 내 일 " + st.items.per_meeting);
        $("stats").textContent = parts.join(" · ");
      }).catch(function () {});
    }).catch(fail("in-msg"));
  }
  function openInput(id) {
    state.detail = id;
    return api("/api/inputs/" + id).then(function (inp) {
      var box = $("input-detail"), y = window.scrollY, same = box.dataset.sig === id + ":" + inp.status + ":" + inp.items.length + ":" + inp.me_speaker;
      if (same && !box.hidden) {  // 바뀐 게 없으면 다시 그리지 않는다 (처리 중 몇 초마다 새로고침될 때 화면이 튀지 않게)
        if (inp.status !== "extracted" && inp.status !== "failed") { clearTimeout(state.poll); state.poll = setTimeout(function () { refresh(true); }, 2500); }
        return;
      }
      box.dataset.sig = id + ":" + inp.status + ":" + inp.items.length + ":" + inp.me_speaker;
      box.textContent = ""; box.hidden = false; $("inputs-list").hidden = true;
      box.appendChild(btn("‹ 목록으로", "link", loadInputs));
      box.appendChild(el("h2", "", inp.title || KIND[inp.kind]));
      var m = el("div", "meta"); m.appendChild(el("span", "tag", KIND[inp.kind])); m.appendChild(el("span", "tag", nice(inp.received_date))); m.appendChild(el("span", "tag", STATUS[inp.status] || inp.status)); box.appendChild(m);
      if (inp.error) box.appendChild(el("p", "msg err", inp.error));
      if (!inp.speakers.length && /\.(m4a|mp3|wav|webm|ogg|aac|amr|3gp|mp4|flac)$/i.test(inp.source_name || "") && inp.status === "extracted")
        box.appendChild(el("p", "msg", "녹음 파일은 누가 말했는지 나뉘지 않아요. 회의는 녹음 앱에서 글로 바꾼 뒤 공유하면 내 일·맡긴 일이 더 정확해요."));
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
      if (inp.summary) { box.appendChild(el("h2", "", "요약")); var sb = el("div", "summary"); sb.appendChild(bullets(inp.summary)); box.appendChild(sb); }
      if (inp.has_minutes) { box.appendChild(el("h2", "", "회의록")); box.appendChild(minutesView(inp)); }
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
      var reset = btn("처음부터 다시 뽑기", "", function () {
        if (!reset.dataset.sure) { reset.dataset.sure = "1"; reset.textContent = "고른 것까지 지우고 다시 뽑아요. 한 번 더"; return; }
        api("/api/inputs/" + id, { method: "PATCH", json: { reset: true } }).then(function () { setTimeout(function () { openInput(id); }, 1500); }).catch(fail("in-msg"));
      });
      act.appendChild(reset);
      var del = btn("이 녹음 지우기", "danger", function () {
        if (del.dataset.sure) { api("/api/inputs/" + id, { method: "DELETE" }).then(loadInputs); return; }
        del.dataset.sure = "1"; del.textContent = "한 번 더 누르면 지워요";
      });
      act.appendChild(del); box.appendChild(act);
      box.appendChild(el("p", "msg", "다시 뽑기: 아직 고르지 않은 것만 새로 만들어요(안 함으로 넘긴 건 다시 안 나와요). 처음부터 다시 뽑기: 이 녹음의 할 일을 모두 지우고 새로 만들어요. 녹음을 지워도 이미 고른 일은 남아요."));
      window.scrollTo(0, y);
      clearTimeout(state.poll);
      if (inp.status !== "extracted" && inp.status !== "failed") state.poll = setTimeout(function () { refresh(true); }, 2500);  // 처리 중이면 상태가 바뀔 때까지 지켜본다
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
    function ensure(sel, id, name) { if (id && !Array.prototype.some.call(sel.options, function (o) { return o.value === id; })) { var o = document.createElement("option"); o.value = id; o.textContent = name || id; sel.appendChild(o); } }
    var src = $("cal-source"), tgt = $("cal-target"), rs = c.read_source || {}, wt = c.write_target || {};
    ensure(tgt, wt.id, wt.name); tgt.value = wt.id || ""; ensure(src, rs.id, rs.name); src.value = rs.id || "";
    say("cal-source-msg", "올리기: " + (wt.name || "기본 캘린더") + " · 가져오기: " + (rs.id ? (rs.name || rs.id) : "올리는 캘린더와 같게") + (linked ? "  — 다른 캘린더를 쓰려면 목록을 불러와 고르세요." : ""));
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
  $("cal-source-load").addEventListener("click", function () {
    say("cal-source-msg", "캘린더 목록을 읽고 있어요…");
    api("/api/calendar/sources").then(function (r) {
      var src = $("cal-source"), tgt = $("cal-target"), keep = src.value, keepT = tgt.value; src.textContent = ""; tgt.textContent = "";
      var o0 = document.createElement("option"); o0.value = ""; o0.textContent = "올리는 캘린더와 같게"; src.appendChild(o0);
      r.sources.forEach(function (c) {
        var o = document.createElement("option"); o.value = c.id; o.textContent = c.name + (c.primary ? " (기본)" : ""); src.appendChild(o);
        var t = document.createElement("option"); t.value = c.id; t.textContent = c.name + (c.primary ? " (기본)" : ""); tgt.appendChild(t);
      });
      src.value = keep; tgt.value = keepT; say("cal-source-msg", r.sources.length + "개 캘린더를 찾았어요. 골라 주세요.");
    }).catch(function (e) { say("cal-source-msg", e.message, true); });
  });
  $("cal-target").addEventListener("change", function () {
    var t = $("cal-target"), name = t.options[t.selectedIndex] ? t.options[t.selectedIndex].textContent.replace(" (기본)", "") : "";
    api("/api/calendar/target", { method: "POST", json: { id: t.value, name: name } }).then(function (c) { renderCal(c); refresh(); }).catch(function (e) { say("cal-source-msg", e.message, true); });
  });
  $("cal-source").addEventListener("change", function () {
    var src = $("cal-source"), name = src.options[src.selectedIndex] ? src.options[src.selectedIndex].textContent.replace(" (기본)", "") : "";
    api("/api/calendar/source", { method: "POST", json: { id: src.value, name: src.value ? name : "" } }).then(function (c) { renderCal(c); refresh(); }).catch(function (e) { say("cal-source-msg", e.message, true); });
  });
  $("cal-unlink").addEventListener("click", function () {
    api("/api/calendar", { method: "DELETE" }).then(renderCal).catch(function (e) { $("cal-err").textContent = e.message; });
  });

  /* ---------- 업데이트 ---------- */
  $("btn-update").addEventListener("click", function () {
    var b = $("btn-update"); b.disabled = true; say("update-msg", "업데이트가 있는지 보고 있어요…");
    api("/api/update", { method: "POST" }).then(function (r) {
      say("update-msg", (r.messages || []).join("\n"));
      if (!r.restarting) { b.disabled = false; return; }
      var was = state.me && state.me.version, tries = 0, limit = r.waiting ? 600 : 30;
      say("update-msg", (r.waiting ? "업데이트했어요. 처리 중인 녹음 " + r.waiting + "건이 끝나면 다시 켜요.\n" : "업데이트했어요. 다시 켜는 중… (10초쯤)\n") + (r.log || []).map(function (l) { return "· " + l; }).join("\n"));
      (function poll() {
        setTimeout(function () {
          api("/api/me").then(function (me) {
            if (me.version && me.version !== was) { location.reload(); return; }
            if (++tries < limit) poll(); else { say("update-msg", "다시 켜지는 데 시간이 걸려요. 잠시 뒤 새로고침해 주세요.", true); b.disabled = false; }
          }).catch(function () { if (++tries < limit) poll(); else { say("update-msg", "서버가 다시 켜지지 않았어요. PC의 말한대로 창을 확인해 주세요.", true); b.disabled = false; } });
        }, 2000);
      })();
    }).catch(function (e) { say("update-msg", e.message, true); b.disabled = false; });
  });

  /* ---------- 달력 ---------- */
  function shiftYm(ym, n) { var p = ym.split("-"); var d = new Date(+p[0], +p[1] - 1 + n, 1); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"); }
  function loadMonth() {
    state.ym = state.ym || state.date.slice(0, 7);
    return api("/api/month?ym=" + state.ym).then(function (m) {
      $("m-title").textContent = m.ym.replace("-", "년 ") + "월";
      var g = $("m-grid"); g.innerHTML = "";
      ["월", "화", "수", "목", "금", "토", "일"].forEach(function (w) { g.appendChild(el("div", "wd", w)); });
      var first = new Date(+m.ym.slice(0, 4), +m.ym.slice(5) - 1, 1);
      for (var i = 0; i < (first.getDay() + 6) % 7; i++) g.appendChild(el("div", "pad"));
      m.days.forEach(function (d) {
        var c = btn("", "day" + (d.date === m.today ? " today" : "") + (d.date > m.today ? " future" : "") + (d.score ? " s" + d.score : ""), function () {
          state.date = d.date; state.tab = "today";
          Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (x) { x.classList.toggle("on", x.dataset.tab === "today"); });
          $("tab-month").hidden = true; $("tab-today").hidden = false; document.querySelector(".top").hidden = false; $("week").hidden = false;
          refresh();
        });
        c.appendChild(el("span", "n", String(+d.date.slice(8))));
        c.appendChild(el("span", "m", d.mood || (d.closed ? "·" : "")));
        c.appendChild(el("span", "c", (d.done || d.left) ? d.done + "·" + d.left : ""));
        c.title = d.date + (d.note ? " — " + d.note : "");
        g.appendChild(c);
      });
      var lv = m.score >= 80 ? ["🌳", "무럭무럭이에요"] : m.score >= 60 ? ["🌷", "활짝 피었어요"] : m.score >= 40 ? ["🌿", "쑥쑥 자라요"] : m.score >= 15 ? ["🌱", "싹이 텄어요"] : ["🫘", "씨앗이에요"];
      $("m-face").textContent = lv[0]; $("m-level").textContent = lv[1];
      $("m-line").textContent = "이달 " + m.active_days + "일 함께했어요" + (m.streak >= 2 ? " · 🔥 " + m.streak + "일째" : "");
      $("m-sub").textContent = m.done_total ? "마친 일 " + m.done_total + "개" + (m.left_total ? " · 남은 일 " + m.left_total + "개" : "") : "";
      var like = $("m-like"); like.hidden = !m.post_url; if (m.post_url) like.href = m.post_url;
    }).catch(fail("in-msg"));
  }
  $("m-prev").addEventListener("click", function () { state.ym = shiftYm(state.ym, -1); loadMonth(); });
  $("m-next").addEventListener("click", function () { state.ym = shiftYm(state.ym, 1); loadMonth(); });

  /* ---------- 탭 ---------- */
  Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (b) {
    b.addEventListener("click", function () {
      state.tab = b.dataset.tab; clearTimeout(state.poll);
      Array.prototype.forEach.call(document.querySelectorAll(".tabs button"), function (x) { x.classList.toggle("on", x === b); });
      $("tab-today").hidden = state.tab !== "today"; $("tab-later").hidden = state.tab !== "later"; $("tab-inputs").hidden = state.tab !== "inputs"; $("tab-month").hidden = state.tab !== "month";
      document.querySelector(".top").hidden = state.tab !== "today"; $("week").hidden = state.tab !== "today";
      if (state.tab !== "today") $("btn-add").hidden = true;
      refresh();
    });
  });
  document.addEventListener("visibilitychange", function () { if (!document.hidden && state.me) refresh(); });

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});
  boot();
})();
