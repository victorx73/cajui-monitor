// Acorda o servidor (plano grátis dorme) assim que a tela de login abre
fetch("/health").catch(() => {});
document.getElementById("form-login").addEventListener("submit", (e) => {
  const b = e.target.querySelector("button");
  b.disabled = true;
  b.textContent = "Entrando…";
});
