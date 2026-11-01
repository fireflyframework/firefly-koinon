// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
// @ts-check
(() => {
  /** @typedef {Record<string, unknown>} ObjectValue */
  /** @typedef {{id:string,revision:number,tenant_id:string,authorization_digest:string,action:string,target_item_id:string,destination:ObjectValue,before:ObjectValue|null,after:ObjectValue,evidence:ObjectValue[],receipt?:ObjectValue|null}} Intent */
  /** @typedef {{id:string,status:string,expires_at:string,review:Intent}} Review */
  /** @typedef {{resolve:(value:ObjectValue)=>void,reject:(reason:Error)=>void,timer:ReturnType<typeof setTimeout>}} Pending */
  const byId = (/** @type {string} */ id) => {
    const element = document.getElementById(id);
    if (!element) throw new Error("Review interface is incomplete");
    return element;
  };
  const checkbox = /** @type {HTMLInputElement} */ (byId("approve-confirm"));
  const approve = /** @type {HTMLButtonElement} */ (byId("approve"));
  const cancel = /** @type {HTMLButtonElement} */ (byId("cancel"));
  const checkStatus = /** @type {HTMLButtonElement} */ (byId("check-status"));
  /** @type {Map<string, Pending>} */ const pending = new Map();
  /** @type {Review|null} */ let current = null;
  /** @type {'text'|'file'|null} */ let reviewMode = null;
  let challenge = "",
    connected = false,
    busy = false,
    uncertain = false,
    decisionKey = "",
    sequence = 0;
  let theme = "light";
  /** @type {unknown} */ let lastPresentation = null;
  const canonicalMark = document.querySelector(".brand-mark")?.cloneNode(true);
  const object = (/** @type {unknown} */ value) =>
    value !== null && typeof value === "object" && !Array.isArray(value)
      ? /** @type {ObjectValue} */ (value)
      : null;
  const text = (/** @type {unknown} */ value) =>
    typeof value === "string" ? value : "Not recorded";
  const set = (/** @type {string} */ id, /** @type {unknown} */ value) => {
    byId(id).textContent = text(value);
  };
  function notify(
    /** @type {string} */ method,
    /** @type {ObjectValue} */ params = {},
  ) {
    window.parent.postMessage({ jsonrpc: "2.0", method, params }, "*");
  }
  function request(
    /** @type {string} */ method,
    /** @type {ObjectValue} */ params,
    timeout = 30000,
  ) {
    const id = "koinon-review-" + ++sequence;
    return new Promise(
      (/** @type {(value:ObjectValue)=>void} */ resolve, reject) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error("Chat application did not respond"));
        }, timeout);
        pending.set(id, { resolve, reject, timer });
        window.parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
      },
    );
  }
  function error(/** @type {string} */ message) {
    set("error", message);
    byId("error").hidden = false;
  }
  function controls() {
    const active =
      connected &&
      current?.status === "preview" &&
      new Date(current.expires_at).getTime() > Date.now() &&
      !!challenge &&
      !busy &&
      !uncertain;
    approve.disabled = !active || !checkbox.checked;
    cancel.disabled = !active;
    checkbox.disabled = !active;
    checkStatus.hidden = !uncertain;
    checkStatus.disabled = busy || !connected;
  }
  function view(/** @type {unknown} */ value) {
    const outer = object(value),
      intent = object(outer?.["review"]);
    if (
      !outer ||
      !intent ||
      typeof outer["id"] !== "string" ||
      typeof outer["status"] !== "string" ||
      typeof intent["tenant_id"] !== "string" ||
      typeof intent["target_item_id"] !== "string" ||
      !Number.isInteger(intent["revision"]) ||
      typeof intent["authorization_digest"] !== "string" ||
      !/^[a-f0-9]{64}$/.test(intent["authorization_digest"]) ||
      !object(intent["destination"]) ||
      !object(intent["after"]) ||
      !Array.isArray(intent["evidence"])
    )
      return null;
    return /** @type {Review} */ (/** @type {unknown} */ (outer));
  }
  function presentation(/** @type {unknown} */ value) {
    const data = object(value);
    if (!data) return;
    lastPresentation = value;
    if (data["font_family"] === "Inter" || data["font_family"] === "Manrope")
      document.documentElement.style.setProperty("--interface-font", data["font_family"]);
    if (typeof data["product_name"] === "string") {
      set("product-name", data["product_name"]);
      byId("product-name").title = data["product_name"];
    }
    const mark = document.querySelector(".brand-mark"),
      symbol = data["symbol"];
    if (mark) {
      if (
        typeof symbol === "string" &&
        symbol.length <= 65536 &&
        /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]+=*$/.test(symbol)
      ) {
        const image = document.createElement("img");
        image.alt = "";
        image.src = symbol;
        image.addEventListener(
          "error",
          () => {
            mark.textContent = text(data["product_name"])
              .slice(0, 1)
              .toUpperCase();
          },
          { once: true },
        );
        mark.replaceChildren(image);
      } else if (
        typeof data["product_name"] === "string" &&
        data["product_name"].toLowerCase() !== "koinon"
      )
        mark.textContent = data["product_name"].slice(0, 1).toUpperCase();
      else if (canonicalMark)
        mark.replaceChildren(
          ...Array.from(canonicalMark.cloneNode(true).childNodes),
        );
    }
    const palettes = object(data["palette"]),
      palette = object(palettes?.[theme]) ?? palettes;
    if (!palette) return;
    const variables = {
      canvas: "--canvas",
      surface: "--surface",
      text: "--text",
      muted: "--muted",
      line: "--line",
      action: "--action",
      action_text: "--action-text",
      accent: "--accent",
    };
    for (const [key, variable] of Object.entries(variables)) {
      const color = palette[key];
      if (typeof color === "string" && /^#[a-f0-9]{6}$/i.test(color))
        document.documentElement.style.setProperty(variable, color);
    }
  }
  function hostContext(/** @type {unknown} */ value) {
    const context = object(value);
    if (context?.["theme"] !== "light" && context?.["theme"] !== "dark") return;
    theme = context["theme"];
    document.documentElement.dataset["theme"] = theme;
    document.documentElement.style.colorScheme = theme;
    presentation(lastPresentation);
  }
  function render(/** @type {Review} */ value) {
    current = value;
    const intent = value.review;
    /** @type {Record<string,string>} */ const actions = {
      create_draft: "Create draft",
      create_published: "Publish knowledge",
      update_draft: "Update draft",
      update_published: "Update published knowledge",
      publish_draft: "Publish draft",
    };
    set("review-title", intent.after["title"]);
    set("action", actions[intent.action] ?? intent.action);
    set("destination", intent.destination["name"]);
    content("before-content", intent.before);
    byId("before-panel").hidden = !intent.before;
    content("after-content", intent.after);
    set("review-id", value.id);
    set("revision", String(intent.revision));
    set("digest", intent.authorization_digest);
    const expires = new Date(value.expires_at);
    set(
      "expires",
      Number.isNaN(expires.getTime())
        ? "Not recorded"
        : expires.toLocaleString(),
    );
    const sources = byId("sources");
    sources.replaceChildren();
    for (const evidence of intent.evidence) {
      const item = document.createElement("li"),
        source = object(evidence["source"]);
      item.textContent = source
        ? [
            "Source " + text(source["asset_id"] ?? source["source_id"]),
            "Revision " + text(source["used_revision"]),
            "Part " + text(source["source_part_id"] ?? source["chunk_id"]),
          ].join(", ")
        : "External proposal. No independently verified source recorded.";
      sources.append(item);
      const details = document.createElement("details"),
        summary = document.createElement("summary"),
        raw = document.createElement("pre");
      summary.textContent = "Recorded provenance";
      raw.textContent = JSON.stringify(evidence, null, 2);
      details.append(summary, raw);
      item.append(details);
    }
    byId("review-content").hidden = false;
    set(
      "description",
      value.status === "committed"
        ? "Your approval and the saved knowledge receipt have been recorded."
        : value.status === "preview"
          ? "Review the exact content, destination and sources. Nothing is saved until you approve."
          : value.status === "cancelled"
            ? "This change was cancelled. Nothing was saved."
            : "The save outcome is not confirmed. Check its recorded status before submitting another change.",
    );
    set(
      "state-label",
      value.status === "committed"
        ? "Saved"
        : value.status === "cancelled"
          ? "Cancelled"
          : value.status === "preview"
            ? "Awaiting approval"
            : "Check status",
    );
    if (value.status === "committed") {
      set(
        "message",
        "Knowledge saved. Version " +
          String(intent.receipt?.["version"] ?? "not recorded") +
          ".",
      );
      challenge = "";
      uncertain = false;
    } else if (value.status === "cancelled") {
      set("message", "Change cancelled. No knowledge was saved.");
      challenge = "";
      uncertain = false;
    } else if (value.status !== "preview") {
      set(
        "message",
        "The outcome needs to be checked before another change is submitted.",
      );
      uncertain = true;
    }
    controls();
  }
  function content(
    /** @type {string} */ id,
    /** @type {ObjectValue|null} */ value,
  ) {
    const container = byId(id);
    container.replaceChildren();
    if (!value) return;
    const title = document.createElement("strong"),
      summary = document.createElement("p"),
      metadata = document.createElement("p"),
      body = document.createElement("div");
    title.textContent = text(value["title"]);
    summary.textContent =
      typeof value["summary"] === "string"
        ? value["summary"]
        : "No summary recorded";
    metadata.textContent =
      "Domain: " +
      text(value["domain"]) +
      ". Tags: " +
      (Array.isArray(value["tags"])
        ? value["tags"].map(text).join(", ") || "None"
        : "Not recorded");
    metadata.className = "content-meta";
    summary.className = "content-summary";
    body.textContent = text(value["body"]);
    container.append(title, summary, metadata, body);
  }
  const fileFlow = createKoinonFileReview({
    request,
    presentation,
    set,
    error,
    activate: () => {
      current = null;
      challenge = "";
      byId("review-content").hidden = true;
      byId("message").textContent = "";
      byId("error").hidden = true;
    },
  });
  function result(/** @type {ObjectValue} */ response, initial = false) {
    const structured = object(response["structuredContent"]),
      meta = object(response["_meta"]),
      privateReview = object(meta?.["koinon/knowledgeReview"]),
      kind = privateReview?.["kind"] ?? structured?.["kind"],
      incomingMode =
        kind === "file" || kind === "file_upload" ? "file" : "text";
    // A component belongs to its initiating tool; late results cannot change its purpose.
    if (reviewMode && reviewMode !== incomingMode) return;
    if (fileFlow.receive(response)) {
      reviewMode = "file";
      return;
    }
    if (response["isError"] === true)
      throw new Error("Knowledge change was denied");
    let value =
      view(privateReview?.["review"]) ??
      view(structured?.["review"]) ??
      view(structured);
    if (!value && current && structured?.["status"] === "committed") {
      const receipt = object(structured["receipt"]);
      if (!receipt) throw new Error("The saved receipt is incomplete");
      value = {
        ...current,
        status: "committed",
        review: { ...current.review, receipt },
      };
    }
    if (
      !value &&
      current &&
      structured?.["status"] === "pending" &&
      structured["intent_id"] === current.id &&
      structured["operation_id"] === current.id
    ) {
      challenge = "";
      uncertain = true;
      value = { ...current, status: "unresolved" };
    }
    if (!value) throw new Error("The review response is incomplete");
    if (value.status === "committed") {
      const receipt = object(value.review.receipt);
      if (
        !receipt ||
        receipt["operation_id"] !== value.id ||
        receipt["intent_id"] !== value.id ||
        receipt["intent_revision"] !== value.review.revision ||
        receipt["authorization_digest"] !== value.review.authorization_digest ||
        receipt["item_id"] !== value.review.target_item_id ||
        receipt["action"] !== value.review.action ||
        !Number.isInteger(receipt["version"]) ||
        Number(receipt["version"]) < 1
      )
        throw new Error("The saved receipt does not match this review");
    }
    reviewMode = "text";
    byId("file-content").hidden = true;
    if (current && current.id !== value.id && !initial)
      throw new Error("A different review was returned");
    const changed =
      current &&
      value.status === "preview" &&
      (current.id !== value.id ||
        current.review.revision !== value.review.revision ||
        current.review.authorization_digest !==
          value.review.authorization_digest);
    if (initial || changed) {
      challenge =
        typeof privateReview?.["nonce"] === "string"
          ? privateReview["nonce"]
          : "";
      decisionKey = "";
      checkbox.checked = false;
      uncertain = false;
      presentation(privateReview?.["presentation"]);
    }
    render(value);
    if (initial && value.status === "preview" && !challenge)
      error(
        "This chat application did not provide a private approval channel. Nothing can be saved from this view.",
      );
  }
  async function act(/** @type {'approve'|'cancel'|'status'} */ action) {
    if (!current || busy || !connected) return;
    if (
      action !== "status" &&
      (!challenge || uncertain || current.status !== "preview")
    )
      return;
    if (action === "approve" && !checkbox.checked) return;
    const selected = current,
      intent = selected.review;
    busy = true;
    byId("error").hidden = true;
    controls();
    /** @type {ObjectValue} */ const args = {
      tenant_id: intent.tenant_id,
      review_id: selected.id,
    };
    if (action !== "status")
      Object.assign(args, {
        expected_revision: intent.revision,
        authorization_digest: intent.authorization_digest,
        nonce: challenge,
      });
    if (action === "approve") {
      decisionKey ||= crypto.randomUUID();
      args["idempotency_key"] = decisionKey;
    }
    try {
      result(
        await request("tools/call", {
          name:
            action === "approve"
              ? "koinon_approve_knowledge"
              : action === "cancel"
                ? "koinon_cancel_knowledge"
                : "koinon_review_status",
          arguments: args,
        }),
      );
      if (action === "status" && current?.status === "preview") {
        uncertain = true;
        set(
          "message",
          "The change is not recorded as saved. Request a fresh review before approving again.",
        );
      }
    } catch {
      uncertain = true;
      error(
        "This change could not be saved or confirmed. Check status and your current permissions before trying again.",
      );
    } finally {
      busy = false;
      controls();
    }
  }
  window.addEventListener("message", (event) => {
    if (event.source !== window.parent) return;
    const data = object(event.data);
    if (!data || data["jsonrpc"] !== "2.0") return;
    const id = typeof data["id"] === "string" ? data["id"] : "",
      waiting = pending.get(id);
    if (waiting) {
      pending.delete(id);
      clearTimeout(waiting.timer);
      const value = object(data["result"]);
      if (value && !data["error"]) waiting.resolve(value);
      else waiting.reject(new Error("Chat application rejected the request"));
      return;
    }
    if (!connected) return;
    if (data["method"] === "ui/notifications/host-context-changed") {
      hostContext(data["params"]);
      return;
    }
    if (data["method"] === "ui/notifications/tool-result") {
      if (busy) return;
      try {
        const params = object(data["params"]);
        if (params) result(params, !current);
      } catch {
        challenge = "";
        error("The review could not be verified. Request a new review.");
        controls();
      }
    } else if (data["method"] === "ui/notifications/tool-cancelled") {
      challenge = "";
      error(
        "The review was cancelled by your chat application. No approval was sent.",
      );
      controls();
    } else if (data["method"] === "ping" && data["id"] !== undefined)
      window.parent.postMessage(
        { jsonrpc: "2.0", id: data["id"], result: {} },
        "*",
      );
  });
  checkbox.addEventListener("change", controls);
  approve.addEventListener("click", () => void act("approve"));
  cancel.addEventListener("click", () => void act("cancel"));
  checkStatus.addEventListener("click", () => void act("status"));
  new ResizeObserver(() =>
    notify("ui/notifications/size-changed", {
      height: document.documentElement.scrollHeight,
    }),
  ).observe(document.body);
  controls();
  setInterval(controls, 5000);
  if (window.parent === window) {
    error(
      "This chat application does not support interactive knowledge review. Nothing was saved.",
    );
    return;
  }
  void request(
    "ui/initialize",
    {
      protocolVersion: "2026-01-26",
      appInfo: { name: byId("product-name").textContent + " review", version: "26.11.1" },
      appCapabilities: {},
    },
    4500,
  )
    .then((value) => {
      if (
        value["protocolVersion"] !== "2026-01-26" ||
        !object(value["hostCapabilities"])
      )
        throw new Error("Unsupported review protocol");
      hostContext(value["hostContext"]);
      connected = true;
      set("state-label", "Ready");
      notify("ui/notifications/initialized");
      controls();
    })
    .catch(() => {
      challenge = "";
      error(
        "This chat application does not support interactive knowledge review. Nothing was saved.",
      );
      controls();
    });
})();
