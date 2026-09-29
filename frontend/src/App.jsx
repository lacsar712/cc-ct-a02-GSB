import { createSignal, onMount, Show, For, createEffect } from "solid-js";
import {
  clearSession,
  createSubmission,
  fetchLimit,
  fetchLimitHistory,
  fetchSubmission,
  fetchSubmissions,
  getUser,
  login,
  setSession,
  updateLimit,
} from "./api";

const statusLabel = {
  pending: "待复核",
  processing: "复核中",
  done: "已完成",
};

const roleLabel = {
  machinist: "操作员",
  auditor: "复核员",
};

function readHash() {
  const raw = (location.hash || "#/").replace(/^#/, "") || "/";
  const m = raw.match(/^\/detail\/(\d+)/);
  if (m) return { name: "detail", id: Number(m[1]) };
  if (raw === "/limit") return { name: "limit", id: null };
  return { name: "home", id: null };
}

function fmtTime(t) {
  return t ? new Date(t).toLocaleString() : "—";
}

function App() {
  const [user, setUser] = createSignal(getUser());
  const [rows, setRows] = createSignal([]);
  const [detail, setDetail] = createSignal(null);
  const [route, setRoute] = createSignal(readHash());
  const [error, setError] = createSignal("");
  const [loading, setLoading] = createSignal(false);

  const [loginUser, setLoginUser] = createSignal("machinist");
  const [loginPass, setLoginPass] = createSignal("machine123456");

  const [toolCode, setToolCode] = createSignal("");
  const [offsetUm, setOffsetUm] = createSignal("");

  const [limit, setLimit] = createSignal(null);
  const [history, setHistory] = createSignal([]);
  const [newLimit, setNewLimit] = createSignal("");

  function goHome() {
    location.hash = "#/";
  }

  function goDetail(id) {
    location.hash = `#/detail/${id}`;
  }

  function goLimit() {
    location.hash = "#/limit";
  }

  async function loadRows() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchSubmissions();
      setRows(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id) {
    setLoading(true);
    setError("");
    try {
      setDetail(await fetchSubmission(id));
    } catch (e) {
      setError(e.message);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadLimitPage() {
    setLoading(true);
    setError("");
    try {
      const [l, h] = await Promise.all([fetchLimit(), fetchLimitHistory()]);
      setLimit(l);
      setHistory(h);
      setNewLimit(String(l.limit_um));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  onMount(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  });

  createEffect(() => {
    const r = route();
    if (!user()) return;
    if (r.name === "detail" && r.id) loadDetail(r.id);
    else if (r.name === "limit") loadLimitPage();
    else loadRows();
  });

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await login(loginUser(), loginPass());
      setSession(data.token, {
        username: data.username,
        role: data.role,
        can_write: data.can_write,
      });
      setUser(getUser());
      goHome();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setRows([]);
    setDetail(null);
    setLimit(null);
    setHistory([]);
    goHome();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await createSubmission(toolCode(), offsetUm());
      setToolCode("");
      setOffsetUm("");
      await loadRows();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleChangeLimit(e) {
    e.preventDefault();
    setError("");
    const value = Number(newLimit());
    if (!Number.isInteger(value) || value < 0) {
      setError("上限必须是不小于 0 的整数微米");
      return;
    }
    try {
      const l = await updateLimit(value);
      setLimit(l);
      setHistory(await fetchLimitHistory());
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <h1>数控刀补复核台</h1>
          <p class="hint">
            刀补绝对值不大于现行合格上限判合格，超过判超差。上限在上限台调整并留改档痕迹：待复核新单吃最新上限，已领取的单沿用领取当时记下的上限。
          </p>
        </div>
        <Show when={user()}>
          <nav class="topnav">
            <a
              href="#/"
              class={route().name === "home" ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                goHome();
              }}
            >
              复核总览
            </a>
            <a
              href="#/limit"
              class={route().name === "limit" ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                goLimit();
              }}
            >
              上限台
            </a>
          </nav>
        </Show>
      </header>

      <Show when={error()}>
        <div class="banner error">{error()}</div>
      </Show>

      <Show
        when={user()}
        fallback={
          <section class="card">
            <h2>登录</h2>
            <form onSubmit={handleLogin} class="form">
              <label>
                用户名
                <input
                  value={loginUser()}
                  onInput={(e) => setLoginUser(e.currentTarget.value)}
                />
              </label>
              <label>
                密码
                <input
                  type="password"
                  value={loginPass()}
                  onInput={(e) => setLoginPass(e.currentTarget.value)}
                />
              </label>
              <button type="submit">进入系统</button>
            </form>
            <p class="hint">操作员 machinist / machine123456；复核员 auditor / audit123456（只读）</p>
          </section>
        }
      >
        <section class="card toolbar">
          <div>
            当前用户：<strong>{user().username}</strong>（{roleLabel[user().role] || user().role}）
          </div>
          <button type="button" class="ghost" onClick={handleLogout}>
            退出
          </button>
        </section>

        <Show when={route().name === "home"}>
          <Show when={user().can_write}>
            <section class="card">
              <h2>提交刀补</h2>
              <form onSubmit={handleSubmit} class="form inline">
                <label>
                  刀具编号
                  <input
                    placeholder="如 T01"
                    value={toolCode()}
                    onInput={(e) => setToolCode(e.currentTarget.value)}
                    required
                  />
                </label>
                <label>
                  刀补（微米）
                  <input
                    type="number"
                    value={offsetUm()}
                    onInput={(e) => setOffsetUm(e.currentTarget.value)}
                    required
                  />
                </label>
                <button type="submit">提交待复核</button>
              </form>
            </section>
          </Show>

          <section class="card">
            <div class="toolbar">
              <h2>复核列表</h2>
              <button type="button" class="ghost" onClick={loadRows} disabled={loading()}>
                {loading() ? "刷新中…" : "刷新"}
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>刀具</th>
                  <th>刀补 µm</th>
                  <th>状态</th>
                  <th>结论</th>
                  <th>认领时上限 µm</th>
                  <th>提交时间</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <For each={rows()}>
                  {(row) => (
                    <tr>
                      <td>{row.tool_code}</td>
                      <td>{row.offset_um}</td>
                      <td>{statusLabel[row.status] || row.status}</td>
                      <td class={row.verdict === "合格" ? "pass" : row.verdict === "超差" ? "fail" : ""}>
                        {row.verdict || "—"}
                      </td>
                      <td>{row.claimed_limit_um == null ? "待领取·吃最新" : row.claimed_limit_um}</td>
                      <td>{fmtTime(row.created_at)}</td>
                      <td>
                        <button type="button" class="ghost" onClick={() => goDetail(row.id)}>
                          详情
                        </button>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={!rows().length && !loading()}>
              <p class="hint">暂无记录</p>
            </Show>
          </section>
        </Show>

        <Show when={route().name === "detail"}>
          <section class="card">
            <div class="toolbar">
              <h2>刀补详情</h2>
              <button type="button" class="ghost" onClick={goHome}>
                返回总览
              </button>
            </div>
            <Show when={detail()} fallback={<p class="hint">{loading() ? "加载中…" : "未找到记录"}</p>}>
              {(d) => (
                <div class="detail-grid">
                  <p>编号：{d().id}</p>
                  <p>刀具：{d().tool_code}</p>
                  <p>刀补 µm：{d().offset_um}</p>
                  <p>状态：{statusLabel[d().status] || d().status}</p>
                  <p class={d().verdict === "合格" ? "pass" : d().verdict === "超差" ? "fail" : ""}>
                    结论：{d().verdict || "—"}
                  </p>
                  <p>
                    认领时上限 µm：
                    {d().claimed_limit_um == null ? "待领取，将吃最新上限" : d().claimed_limit_um}
                  </p>
                  <p>提交时间：{fmtTime(d().created_at)}</p>
                  <p>复核时间：{fmtTime(d().reviewed_at)}</p>
                </div>
              )}
            </Show>
          </section>
        </Show>

        <Show when={route().name === "limit"}>
          <section class="card">
            <div class="toolbar">
              <h2>现行数字</h2>
              <button type="button" class="ghost" onClick={loadLimitPage} disabled={loading()}>
                {loading() ? "刷新中…" : "刷新"}
              </button>
            </div>
            <Show when={limit()} fallback={<p class="hint">加载中…</p>}>
              {(l) => (
                <>
                  <p class="limit-now">
                    现行合格上限：<strong>{l().limit_um}</strong> µm
                  </p>
                  <p class="hint">
                    最近调整：
                    {l().updated_at
                      ? `${l().updated_by || "—"} · ${fmtTime(l().updated_at)}`
                      : "尚未调整过，沿用初始上限"}
                  </p>
                  <Show
                    when={user().can_write}
                    fallback={
                      <p class="hint">复核员只读：只能查看上限与改档痕迹，不能改上限，也不能提交刀补。</p>
                    }
                  >
                    <form onSubmit={handleChangeLimit} class="form inline">
                      <label>
                        新上限（微米）
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={newLimit()}
                          onInput={(e) => setNewLimit(e.currentTarget.value)}
                          required
                        />
                      </label>
                      <button type="submit">改上限并留痕</button>
                    </form>
                  </Show>
                </>
              )}
            </Show>
          </section>

          <section class="card">
            <h2>改档痕迹</h2>
            <table>
              <thead>
                <tr>
                  <th>原上限 µm</th>
                  <th>新上限 µm</th>
                  <th>改档人</th>
                  <th>改档时间</th>
                </tr>
              </thead>
              <tbody>
                <For each={history()}>
                  {(h) => (
                    <tr>
                      <td>{h.old_limit_um}</td>
                      <td>{h.new_limit_um}</td>
                      <td>{h.changed_by || "—"}</td>
                      <td>{fmtTime(h.changed_at)}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={!history().length && !loading()}>
              <p class="hint">暂无改档记录</p>
            </Show>
          </section>

          <section class="card">
            <h2>认领如何吃上限</h2>
            <ul class="rules">
              <li>还在待复核的新单不记上限，被领取那一刻吃<b>最新现行上限</b>。</li>
              <li>已进复核中（或已完成）的单，继续用<b>领取当时记下的上限</b>；之后再改档不影响它。</li>
              <li>判定规则：刀补绝对值不大于上限写「合格」，超过上限写「超差」。</li>
              <li>操作员可改上限，每次改档追加一条痕迹；复核员只能看上限与痕迹，不能改也不能交刀补。</li>
            </ul>
          </section>
        </Show>
      </Show>
    </div>
  );
}

export default App;
