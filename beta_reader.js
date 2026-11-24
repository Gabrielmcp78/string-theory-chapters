<script type="module">
(function() {
  const FIREBASE_CONFIG = {
    apiKey: "AIzaSyAoD2KGxzmazHExX3RPILoCoShwocjcxkw",
    authDomain: "string-theory-reader.firebaseapp.com",
    projectId: "string-theory-reader",
    storageBucket: "string-theory-reader.firebasestorage.app",
    messagingSenderId: "753683051584",
    appId: "1:753683051584:web:ffe959c1a9e9fe40821ba5"
  };

  const INVITE_KEY = "st-invite-code";
  const NAME_KEY = "st-invite-name";

  const params = new URLSearchParams(window.location.search);
  const urlInvite = (params.get("invite") || "").trim();
  if (urlInvite) {
    try { localStorage.setItem(INVITE_KEY, urlInvite); } catch (_) {}
    params.delete("invite");
    const cleanUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "") + window.location.hash;
    window.history.replaceState({}, "", cleanUrl);
  }

  let inviteCode = "";
  try { inviteCode = (localStorage.getItem(INVITE_KEY) || "").trim(); } catch (_) {}

  function getChapterSlug() {
    const m = window.location.pathname.match(/\/chapters\/([^\/]+)\.html$/);
    return m ? m[1] : null;
  }

  function addSignInPrompt() {
    const footer = document.querySelector("footer");
    if (!footer || document.getElementById("st-signin-trigger")) return;
    const btn = document.createElement("button");
    btn.id = "st-signin-trigger";
    btn.className = "st-beta-pill";
    btn.textContent = "Beta Reader Code";
    btn.onclick = function() {
      const code = window.prompt("Enter your beta reader invite code:");
      if (code && code.trim()) {
        try { localStorage.setItem(INVITE_KEY, code.trim()); } catch (_) {}
        window.location.reload();
      }
    };
    footer.appendChild(btn);
  }

  if (!inviteCode) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", addSignInPrompt);
    } else {
      addSignInPrompt();
    }
    return;
  }

  async function initBetaReader() {
    const [{ initializeApp }, fs] = await Promise.all([
      import("https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js")
    ]);
    const app = initializeApp(FIREBASE_CONFIG);
    const db = fs.getFirestore(app);

    // 1. Validate invite
    const inviteRef = fs.doc(db, "invites", inviteCode);
    let inviteSnap;
    try {
      inviteSnap = await fs.getDoc(inviteRef);
    } catch (err) {
      console.warn("Beta invite lookup failed:", err);
      return;
    }
    if (!inviteSnap.exists() || inviteSnap.data().active !== true) {
      try { localStorage.removeItem(INVITE_KEY); localStorage.removeItem(NAME_KEY); } catch (_) {}
      addSignInPrompt();
      return;
    }

    const readerName = String(inviteSnap.data().name || "Reader").trim();
    const isAuthor = inviteSnap.data().role === "author" || inviteCode === "gabriel-test-01";
    try { localStorage.setItem(NAME_KEY, readerName); } catch (_) {}
    document.body.classList.add("st-beta-active");

    const chapterSlug = getChapterSlug();
    const isIndex = !chapterSlug;

    // 2. Render status pill in header or toolbar
    const pillHost = document.querySelector(".reader-controls") || document.querySelector("header .meta") || document.querySelector("header");
    if (pillHost && !document.getElementById("st-reader-pill")) {
      if (isAuthor) {
        const inboxBtn = document.createElement("button");
        inboxBtn.id = "st-inbox-btn";
        inboxBtn.className = "st-beta-pill";
        inboxBtn.textContent = "All Reader Notes";
        pillHost.appendChild(inboxBtn);
      }
      const pill = document.createElement("button");
      pill.id = "st-reader-pill";
      pill.className = "st-beta-pill";
      pill.title = "Signed in as " + readerName + " (click to sign out)";
      pill.innerHTML = '<span class="st-beta-dot"></span><span></span>';
      pill.querySelector("span:last-child").textContent = readerName + " · Synced";
      pill.onclick = function() {
        if (window.confirm("Sign out beta reader mode for " + readerName + "?")) {
          try { localStorage.removeItem(INVITE_KEY); localStorage.removeItem(NAME_KEY); } catch (_) {}
          window.location.reload();
        }
      };
      pillHost.appendChild(pill);
    }

    if (isAuthor) {
      const inboxDrawer = document.createElement("aside");
      inboxDrawer.id = "st-inbox-drawer";
      inboxDrawer.setAttribute("aria-label", "All reader notes");
      inboxDrawer.innerHTML = [
        '<div class="st-drawer-head">',
        '  <span class="st-drawer-title">All Reader Notes</span>',
        '  <button class="st-drawer-close" aria-label="Close">&times;</button>',
        '</div>',
        '<div class="st-drawer-thread" id="st-inbox-body"><div style="opacity:0.65;font-size:0.85rem">Loading notes…</div></div>'
      ].join("");
      document.body.appendChild(inboxDrawer);
      inboxDrawer.querySelector(".st-drawer-close").onclick = function() {
        inboxDrawer.classList.remove("open");
      };
      const inboxBtnEl = document.getElementById("st-inbox-btn");
      if (inboxBtnEl) {
        inboxBtnEl.onclick = async function() {
          inboxDrawer.classList.add("open");
          const bodyEl = document.getElementById("st-inbox-body");
          bodyEl.innerHTML = '<div style="opacity:0.65;font-size:0.85rem">Loading notes…</div>';
          try {
            const snap = await fs.getDocs(fs.query(fs.collection(db, "comments"), fs.limit(500)));
            const all = [];
            snap.forEach(function(d) { all.push(d.data()); });
            if (all.length === 0) {
              bodyEl.innerHTML = '<div style="opacity:0.65;font-size:0.85rem">No reader notes yet.</div>';
              return;
            }
            all.sort(function(a, b) {
              const sc = String(a.chapterSlug || "").localeCompare(String(b.chapterSlug || ""));
              if (sc !== 0) return sc;
              const pd = (Number(a.paragraphIndex) || 0) - (Number(b.paragraphIndex) || 0);
              if (pd !== 0) return pd;
              const ta = a.createdAt && a.createdAt.seconds ? a.createdAt.seconds : 0;
              const tb = b.createdAt && b.createdAt.seconds ? b.createdAt.seconds : 0;
              return ta - tb;
            });
            const grouped = new Map();
            all.forEach(function(c) {
              const key = c.chapterLabel || c.chapterSlug || "Unknown";
              if (!grouped.has(key)) grouped.set(key, []);
              grouped.get(key).push(c);
            });
            bodyEl.innerHTML = "";
            grouped.forEach(function(items, chTitle) {
              const grp = document.createElement("div");
              grp.className = "st-inbox-group";
              const hdr = document.createElement("div");
              hdr.className = "st-inbox-ch-title";
              hdr.textContent = chTitle + " (" + items.length + ")";
              grp.appendChild(hdr);
              items.forEach(function(c) {
                const card = document.createElement("div");
                card.className = "st-comment-item";
                const meta = document.createElement("div");
                meta.className = "st-comment-meta";
                const auth = document.createElement("span");
                auth.className = "st-comment-author";
                auth.textContent = (c.authorName || "Reader") + " · ¶" + ((Number(c.paragraphIndex) || 0) + 1);
                const when = document.createElement("span");
                const dt = c.createdAt && c.createdAt.toDate ? c.createdAt.toDate() : null;
                when.textContent = dt ? dt.toLocaleDateString() : "";
                meta.appendChild(auth);
                meta.appendChild(when);
                const quote = document.createElement("div");
                quote.style.fontSize = "0.76rem";
                quote.style.opacity = "0.72";
                quote.style.fontStyle = "italic";
                quote.style.marginBottom = "0.3rem";
                const pv = String(c.paragraphPreview || "");
                quote.textContent = pv.length > 110 ? "“" + pv.slice(0, 110) + "…”" : (pv ? "“" + pv + "”" : "");
                const txt = document.createElement("div");
                txt.textContent = c.text || "";
                const jump = document.createElement("a");
                jump.className = "st-inbox-jump";
                const prefix = isIndex ? "chapters/" : "";
                jump.href = prefix + encodeURIComponent(c.chapterSlug || "") + ".html?para=" + (Number(c.paragraphIndex) || 0);
                jump.textContent = "Jump to paragraph →";
                card.appendChild(meta);
                if (pv) card.appendChild(quote);
                card.appendChild(txt);
                card.appendChild(jump);
                grp.appendChild(card);
              });
              bodyEl.appendChild(grp);
            });
          } catch (err) {
            bodyEl.innerHTML = '<div style="color:#c66;font-size:0.85rem">Failed to load notes.</div>';
            console.warn("Inbox load failed:", err);
          }
        };
      }
    }

    const readerRef = fs.doc(db, "readers", inviteCode);
    let readerState = {};
    try {
      const rSnap = await fs.getDoc(readerRef);
      if (rSnap.exists()) readerState = rSnap.data() || {};
    } catch (_) {}

    // Restore preferences if saved remotely
    if (readerState.theme && typeof updateThemeUI === "function") {
      const wantDark = readerState.theme === "dark";
      const hasDark = document.documentElement.classList.contains("dark-mode");
      if (wantDark !== hasDark) {
        document.documentElement.classList.toggle("dark-mode", wantDark);
        try { localStorage.setItem("st-theme", readerState.theme); } catch (_) {}
        updateThemeUI(wantDark);
      }
    }
    if (typeof readerState.fontSize === "number" && typeof applyFontSize === "function") {
      applyFontSize(readerState.fontSize);
    }

    // 3. On index page, show "Continue Reading" banner if saved
    if (isIndex && readerState.lastChapterSlug) {
      const header = document.querySelector("header");
      if (header) {
        const banner = document.createElement("div");
        banner.className = "st-resume-banner";
        const label = readerState.lastChapterSlug.replace(/-/g, " ").replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        const pInfo = typeof readerState.lastParagraphIndex === "number" ? " · paragraph " + (readerState.lastParagraphIndex + 1) : "";
        banner.innerHTML = '<span>Welcome back, <strong></strong> — last read <em></em></span><a class="st-resume-btn">Continue Reading &#8594;</a>';
        banner.querySelector("strong").textContent = readerName;
        banner.querySelector("em").textContent = label + pInfo;
        banner.querySelector("a").href = "chapters/" + encodeURIComponent(readerState.lastChapterSlug) + ".html?resume=1";
        header.insertAdjacentElement("afterend", banner);
      }
      return;
    }

    if (!chapterSlug) return;

    // 4. Tag commentable paragraphs in .chapter-text
    const chapterText = document.querySelector(".chapter-text");
    if (!chapterText) return;
    const paras = Array.from(chapterText.querySelectorAll("p")).filter(function(p) {
      if (p.closest(".manuscript-manifest, .chapter-analysis, .chapter-sentinel")) return false;
      if (p.classList.contains("location") || p.classList.contains("tempo-1") || p.classList.contains("tempo-2") || p.classList.contains("scene-break")) return false;
      return (p.textContent || "").trim().length > 0;
    });
    paras.forEach(function(p, idx) {
      p.dataset.paraIdx = String(idx);
      p.classList.add("st-commentable-p");
    });

    // Scroll to saved paragraph if ?resume=1
    if (params.get("resume") === "1" && readerState.lastChapterSlug === chapterSlug && typeof readerState.lastParagraphIndex === "number") {
      const targetP = paras[readerState.lastParagraphIndex];
      if (targetP) {
        setTimeout(function() { targetP.scrollIntoView({ behavior: "smooth", block: "center" }); }, 150);
      }
    }

    // 5. Save reading progress (debounced)
    function currentTopParagraphIndex() {
      const mid = window.innerHeight * 0.3;
      let best = 0;
      for (let i = 0; i < paras.length; i++) {
        const r = paras[i].getBoundingClientRect();
        if (r.top <= mid) best = i;
        else break;
      }
      return best;
    }

    let saveTimer = null;
    async function persistProgress() {
      const theme = document.documentElement.classList.contains("dark-mode") ? "dark" : "light";
      let fsVal = 1.1;
      try { fsVal = parseFloat(localStorage.getItem("st-font-size")) || 1.1; } catch (_) {}
      try {
        await fs.setDoc(readerRef, {
          name: readerName,
          lastChapterSlug: chapterSlug,
          lastParagraphIndex: currentTopParagraphIndex(),
          lastScrollY: Math.round(window.scrollY || 0),
          theme: theme,
          fontSize: fsVal,
          updatedAt: fs.serverTimestamp()
        }, { merge: true });
      } catch (err) {
        console.warn("Progress sync failed:", err);
      }
    }

    function scheduleProgressSave() {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(persistProgress, 1500);
    }
    window.addEventListener("scroll", scheduleProgressSave, { passive: true });
    document.addEventListener("visibilitychange", function() {
      if (document.visibilityState === "hidden") persistProgress();
    });
    persistProgress();

    // 6. Side Comment Card Drawer
    const drawer = document.createElement("aside");
    drawer.id = "st-comment-drawer";
    drawer.setAttribute("aria-label", "Paragraph comments");
    drawer.innerHTML = [
      '<div class="st-drawer-head">',
      '  <span class="st-drawer-title">Paragraph Note</span>',
      '  <button class="st-drawer-close" aria-label="Close">&times;</button>',
      '</div>',
      '<div class="st-drawer-quote"></div>',
      '<div class="st-drawer-thread"></div>',
      '<form class="st-drawer-form">',
      '  <textarea placeholder="Write your note for Gabriel…" maxlength="4000"></textarea>',
      '  <div class="st-drawer-actions">',
      '    <span class="st-drawer-status"></span>',
      '    <button type="submit" class="st-save-btn">Save Note</button>',
      '  </div>',
      '</form>'
    ].join("");
    document.body.appendChild(drawer);

    const quoteEl = drawer.querySelector(".st-drawer-quote");
    const threadEl = drawer.querySelector(".st-drawer-thread");
    const formEl = drawer.querySelector(".st-drawer-form");
    const textareaEl = drawer.querySelector("textarea");
    const statusEl = drawer.querySelector(".st-drawer-status");
    const saveBtn = drawer.querySelector(".st-save-btn");
    const titleEl = drawer.querySelector(".st-drawer-title");
    drawer.querySelector(".st-drawer-close").onclick = function() {
      drawer.classList.remove("open");
      paras.forEach(function(el) { el.classList.remove("st-p-selected"); });
    };

    let activeParaIdx = null;
    const commentsByPara = new Map();

    function renderBadges() {
      paras.forEach(function(p, idx) {
        const old = p.querySelector(".st-p-badge");
        if (old) old.remove();
        const list = commentsByPara.get(idx) || [];
        if (list.length > 0) {
          const badge = document.createElement("span");
          badge.className = "st-p-badge";
          badge.textContent = String(list.length);
          p.appendChild(badge);
        }
      });
    }

    function renderThread(idx) {
      const list = commentsByPara.get(idx) || [];
      threadEl.innerHTML = "";
      if (list.length === 0) {
        const empty = document.createElement("div");
        empty.style.opacity = "0.65";
        empty.style.fontSize = "0.84rem";
        empty.textContent = "No notes on this paragraph yet.";
        threadEl.appendChild(empty);
        return;
      }
      list.forEach(function(c) {
        const item = document.createElement("div");
        item.className = "st-comment-item";
        const meta = document.createElement("div");
        meta.className = "st-comment-meta";
        const author = document.createElement("span");
        author.className = "st-comment-author";
        author.textContent = c.authorName || "Reader";
        const when = document.createElement("span");
        const dt = c.createdAt && c.createdAt.toDate ? c.createdAt.toDate() : null;
        when.textContent = dt ? dt.toLocaleDateString() : "just now";
        meta.appendChild(author);
        meta.appendChild(when);
        const body = document.createElement("div");
        body.textContent = c.text || "";
        item.appendChild(meta);
        item.appendChild(body);
        threadEl.appendChild(item);
      });
    }

    async function loadChapterComments() {
      try {
        const q = fs.query(
          fs.collection(db, "comments"),
          fs.where("chapterSlug", "==", chapterSlug)
        );
        const snap = await fs.getDocs(q);
        commentsByPara.clear();
        snap.forEach(function(d) {
          const data = d.data();
          const idx = Number(data.paragraphIndex);
          if (!Number.isInteger(idx)) return;
          if (!commentsByPara.has(idx)) commentsByPara.set(idx, []);
          commentsByPara.get(idx).push(data);
        });
        commentsByPara.forEach(function(arr) {
          arr.sort(function(a, b) {
            const ta = a.createdAt && a.createdAt.seconds ? a.createdAt.seconds : 0;
            const tb = b.createdAt && b.createdAt.seconds ? b.createdAt.seconds : 0;
            return ta - tb;
          });
        });
        renderBadges();
        if (activeParaIdx !== null) renderThread(activeParaIdx);
      } catch (err) {
        console.warn("Could not load comments:", err);
      }
    }

    paras.forEach(function(p, idx) {
      p.addEventListener("click", function(e) {
        if (e.target && e.target.closest("a")) return;
        activeParaIdx = idx;
        paras.forEach(function(el) { el.classList.remove("st-p-selected"); });
        p.classList.add("st-p-selected");
        titleEl.textContent = "Paragraph " + (idx + 1);
        const raw = (p.textContent || "").trim();
        quoteEl.textContent = raw.length > 200 ? raw.slice(0, 200) + "…" : raw;
        statusEl.textContent = "";
        renderThread(idx);
        drawer.classList.add("open");
        setTimeout(function() { textareaEl.focus(); }, 220);
      });
    });

    formEl.addEventListener("submit", async function(e) {
      e.preventDefault();
      if (activeParaIdx === null) return;
      const text = (textareaEl.value || "").trim();
      if (!text) return;
      saveBtn.disabled = true;
      statusEl.textContent = "Saving…";
      const heading = document.querySelector(".chapter-heading");
      const chNum = document.querySelector(".chapter-number");
      const chapterLabel = [chNum ? chNum.textContent.trim() : "", heading ? heading.textContent.trim() : ""].filter(Boolean).join(": ") || chapterSlug;
      const pText = (paras[activeParaIdx].textContent || "").trim().slice(0, 240);
      const payload = {
        inviteCode: inviteCode,
        authorName: readerName,
        chapterSlug: chapterSlug,
        chapterLabel: chapterLabel.slice(0, 140),
        paragraphIndex: activeParaIdx,
        paragraphPreview: pText,
        text: text,
        status: "open",
        createdAt: fs.serverTimestamp(),
        updatedAt: fs.serverTimestamp()
      };
      try {
        await fs.addDoc(fs.collection(db, "comments"), payload);
        textareaEl.value = "";
        statusEl.textContent = "Saved";
        if (!commentsByPara.has(activeParaIdx)) commentsByPara.set(activeParaIdx, []);
        commentsByPara.get(activeParaIdx).push(payload);
        renderBadges();
        renderThread(activeParaIdx);
      } catch (err) {
        console.error("Comment save failed:", err);
        statusEl.textContent = "Could not save (" + (err.code || "error") + ")";
      } finally {
        saveBtn.disabled = false;
      }
    });

    await loadChapterComments();

    const jumpParaRaw = params.get("para");
    if (jumpParaRaw !== null) {
      const jumpIdx = Number(jumpParaRaw);
      if (Number.isInteger(jumpIdx) && paras[jumpIdx]) {
        setTimeout(function() {
          paras[jumpIdx].scrollIntoView({ behavior: "smooth", block: "center" });
          paras[jumpIdx].click();
        }, 180);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initBetaReader);
  } else {
    initBetaReader();
  }
})();
</script>