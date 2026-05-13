import "./styles.css";

const app = document.querySelector("#app");
const streamlitUrl = "http://127.0.0.1:2280";

app.innerHTML = `
  <main class="shell">
    <section class="hero shell-row">
      <div>
        <p class="eyebrow">zero-native desktop shell</p>
        <h1>ZeroNative RTX 5090</h1>
        <p class="lede">
          This native shell now starts the existing <code>app.py</code> Streamlit app and
          renders it inside the zero-native window.
        </p>
      </div>
      <a class="open-link" href="${streamlitUrl}" target="_blank" rel="noreferrer">Open Streamlit in Browser</a>
    </section>

    <section class="viewer-card">
      <div class="viewer-meta">
        <span>Embedded Streamlit app</span>
        <code>${streamlitUrl}</code>
      </div>
      <iframe class="viewer" src="${streamlitUrl}" title="ZeroNative Streamlit App"></iframe>
    </section>
  </main>
`;
