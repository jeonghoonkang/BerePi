import "./styles.css";

const app = document.querySelector("#app");

app.innerHTML = `
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">zero-native desktop shell</p>
      <h1>ZeroNative RTX 5090</h1>
      <p class="lede">
        This directory now includes a real zero-native project scaffold based on the
        official zero-native structure: <code>app.zon</code>, <code>build.zig</code>,
        <code>src/</code>, and <code>frontend/</code>.
      </p>
    </section>

    <section class="grid">
      <article class="card">
        <h2>What This Is</h2>
        <p>
          A native Zig + WebView shell for the RTX 5090 LLM workspace. It is separate
          from the legacy Streamlit prototype that still lives in this folder.
        </p>
      </article>
      <article class="card">
        <h2>Current Scope</h2>
        <p>
          The native shell is ready for zero-native wiring and frontend iteration.
          The existing Python Streamlit app remains available as the functional prototype.
        </p>
      </article>
      <article class="card">
        <h2>Run Path</h2>
        <p>
          Install <code>zig</code> 0.16+, install the <code>zero-native</code> CLI,
          point <code>third_party/zero-native</code> at the framework source, then run
          <code>zig build run</code> or <code>zig build dev</code>.
        </p>
      </article>
    </section>

    <section class="panel">
      <h2>Project Files</h2>
      <ul>
        <li><code>app.zon</code> for manifest, window, and security policy</li>
        <li><code>build.zig</code> for zero-native build and package flow</li>
        <li><code>src/main.zig</code> and <code>src/runner.zig</code> for the shell</li>
        <li><code>frontend/</code> for the bundled web UI</li>
      </ul>
    </section>
  </main>
`;
