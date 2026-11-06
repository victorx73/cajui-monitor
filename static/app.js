(() => {
  const KEY = "cajui:v1"; // último resultado, guardado só neste aparelho
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Number(n).toFixed(1).replace(".", ",") + "%";
  let temCache = false;

  function render(p) {
    const limite = p.limite;
    const risco = p.geral < limite;
    $("geral").textContent = fmt(p.geral);
    $("geral").className = "overview-value " + (risco ? "danger" : "success");
    $("dot").className = "status-dot" + (risco ? "" : " success");
    $("status-text").textContent = risco ? "Abaixo da frequência mínima" : "Frequência regular";
    $("updated").textContent = "Atualizado às " +
      new Date(p.ts * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

    const emRisco = p.dados.filter((d) => d.percentual < limite).length;
    $("alerta").hidden = emRisco === 0;
    $("alerta-text").textContent =
      emRisco + " disciplina(s) estão abaixo dos " + String(limite).replace(".", ",") + "% de frequência.";

    $("count").textContent = p.dados.length + " disciplinas";
    const lista = $("lista");
    lista.replaceChildren();
    if (!p.dados.length) {
      const e = document.createElement("p");
      e.className = "empty";
      e.textContent = "Nenhuma disciplina encontrada.";
      lista.append(e);
      return;
    }
    for (const d of p.dados) {
      const cls = d.percentual < limite ? "danger" : "success";
      const art = document.createElement("article");
      art.className = "subject";
      art.innerHTML =
        '<div class="subject-top"><h3 class="subject-name"></h3><span class="subject-percent"></span></div>' +
        '<div class="subject-stats"><span><strong class="present"></strong> presenças</span>' +
        '<span><strong class="absent"></strong> faltas</span><span><strong class="tot"></strong> aulas</span></div>' +
        '<div class="progress"><div class="progress-fill"></div></div>';
      art.querySelector(".subject-name").textContent = d.nome; // textContent: sem injeção de HTML
      const pct = art.querySelector(".subject-percent");
      pct.textContent = fmt(d.percentual);
      pct.classList.add(cls);
      art.querySelector(".present").textContent = d.presencas;
      art.querySelector(".absent").textContent = d.faltas;
      art.querySelector(".tot").textContent = d.total;
      const fill = art.querySelector(".progress-fill");
      fill.classList.add(cls);
      fill.style.width = Math.max(0, Math.min(100, d.percentual)) + "%";
      lista.append(art);
    }
  }

  function setBusy(busy) {
    $("refresh").disabled = busy;
    $("refresh-label").textContent = busy ? "Atualizando…" : "Atualizar";
    $("header").classList.toggle("updating-pulse", busy);
  }

  async function load(refresh) {
    setBusy(true);
    $("note").textContent = "";
    const lento = setTimeout(() => {
      $("note").textContent = "Acordando o servidor… pode levar até 1 minuto na primeira vez.";
    }, 4000);
    try {
      const r = await fetch("/api/faltas" + (refresh ? "?refresh=1" : ""), { credentials: "same-origin" });
      if (r.status === 401) {
        localStorage.removeItem(KEY);
        location.replace("/");
        return;
      }
      if (!r.ok) throw new Error("http " + r.status);
      const p = await r.json();
      try { localStorage.setItem(KEY, JSON.stringify(p)); } catch (_) {}
      temCache = true;
      render(p);
      $("note").textContent = "";
    } catch (_) {
      $("note").textContent = temCache
        ? "Não consegui atualizar agora. Exibindo os últimos dados salvos."
        : "Não foi possível carregar os dados. Tente atualizar.";
      if (!temCache) $("lista").replaceChildren();
    } finally {
      clearTimeout(lento);
      setBusy(false);
    }
  }

  $("refresh").addEventListener("click", () => load(true));
  $("sair").addEventListener("click", () => { try { localStorage.removeItem(KEY); } catch (_) {} });

  // 1) mostra na hora o último resultado salvo neste aparelho; 2) atualiza em seguida
  try {
    const salvo = localStorage.getItem(KEY);
    if (salvo) { render(JSON.parse(salvo)); temCache = true; }
  } catch (_) {}
  load(false);
})();
