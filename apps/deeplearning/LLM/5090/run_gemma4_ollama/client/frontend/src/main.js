import "./styles.css";

const app = document.querySelector("#app");
const clientUrl = "http://127.0.0.1:8765";

app.innerHTML = `
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">zero-native desktop shell</p>
        <h1>Gemma4 Prompt Client</h1>
        <p class="lede">
          This native shell embeds the local client service that manages remote prompt chaining,
          config files, and prompt history for <code>run_gemma4_ollama/server</code>.
        </p>
      </div>
      <a class="open-link" href="${clientUrl}" target="_blank" rel="noreferrer">Open Client In Browser</a>
    </section>

    <section class="viewer-card">
      <div class="viewer-meta">
        <span>Embedded local client</span>
        <code>${clientUrl}</code>
      </div>
      <iframe class="viewer" src="${clientUrl}" title="Gemma4 Prompt Client"></iframe>
    </section>
  </main>
`;
