"use strict";
const csrf = document.querySelector('meta[name="cerebellum-csrf"]').content;
const kind = "meta-controller";
let state = { draft:null, snapshots:[], runs:[], config:null, taxonomy:null, expertViews:[], adapters:[], quality:null, qualityModels:[], synthetic:[], topics:[], policies:[], events:[], cards:[], documents:[], jobs:[] };
const eventDetail = new Map();

async function api(path, options={}) {
  const headers = {"Accept":"application/json", "X-Cerebellum-CSRF":csrf, ...(options.headers||{})};
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {...options, headers, credentials:"same-origin"});
  const value = await response.json().catch(()=>({error:`HTTP ${response.status}`}));
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}
function esc(value){ return String(value ?? "").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch])); }
function short(value){ return value ? `${value.slice(0,10)}…${value.slice(-6)}` : "—"; }
function safeLink(url,label){ return /^https:\/\//.test(url) ? `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(label||url)}</a>` : esc(label||url); }
function toast(message){ const node=document.querySelector("#toast"); node.textContent=message; node.classList.add("show"); setTimeout(()=>node.classList.remove("show"),3200); }
async function maybe(path){ try{return await api(path);}catch(error){if(error.message.includes("not found"))return null;throw error;} }

async function refresh(){
  try {
    const eventStatus=document.querySelector("#event-status").value, eventPlatform=document.querySelector("#event-platform").value.trim(), jobStatus=document.querySelector("#job-status").value;
    const eventsQuery=`/v1/events?limit=100${eventStatus!=="all"?`&status=${eventStatus}`:""}${eventPlatform?`&platform=${encodeURIComponent(eventPlatform)}`:""}`;
    const jobsQuery=`/v1/learning/jobs?limit=100${jobStatus!=="all"?`&status=${jobStatus}`:""}`;
    const [draft,snapshots,runs,config,acquisition,taxonomy,expertViews,adapters,quality,qualityModels,synthetic,topics,policies,events,cards,documents,jobs] = await Promise.all([
      maybe(`/v1/datasets/${kind}/draft`), api(`/v1/dataset-snapshots?kind=${kind}`), api("/v1/training-runs"), api("/v1/training-config"), api("/v1/acquisition/status"), api("/v1/expert-taxonomy"), api("/v1/expert-dataset-views?limit=100"), api("/v1/expert-adapters"), api("/v1/quality/status"), api("/v1/quality/model-versions"), api("/v1/synthetic-candidates?limit=100"), api("/v1/topics"), api("/v1/source-policies"), api(eventsQuery), api("/v1/knowledge/cards?limit=50"), api("/v1/documents?limit=50"), api(jobsQuery)
    ]);
    state={draft,snapshots,runs,config,taxonomy,expertViews,adapters,quality,qualityModels,synthetic,topics,policies,events,cards,documents,jobs}; render(acquisition); eventDetail.clear(); renderAcquisition();
  } catch(error){ toast(error.message); }
}
function render(acquisition){
  const build=state.draft?.build;
  document.querySelector("#metrics").innerHTML=[
    [acquisition.document_count,"采集文档"],[acquisition.knowledge_card_count,"知识卡"],[build?.decision_count||0,"训练决策"],[build?.replay_eval_count||0,"合格回放"],[state.quality?.pending_assessments||0,"待 Flash"],[state.quality?.pending_arbitrations||0,"待 Pro"]
  ].map(([v,k])=>`<div class="metric"><strong>${esc(v)}</strong><span>${esc(k)}</span></div>`).join("");
  const q=state.quality,usage=q?.usage;
  document.querySelector("#quality-status").innerHTML=q?.enabled?`<div class="card"><div class="card-head"><strong>${esc(q.provider)} · 本地零成本</strong><span class="pill">${q.enforcement_required?'enforced':'observe'}</span></div><p>Flash ${esc(q.flash_model)} · Pro ${esc(q.pro_model)} · 隔离 ${q.quarantined_records} · 合成候选 ${q.synthetic_candidates}</p><p>cache hit ${usage?.usage?.prompt_cache_hit_tokens||0} / miss ${usage?.usage?.prompt_cache_miss_tokens||0}</p></div>`:"本地 Ornith 质量门禁未启用；现有确定性门禁继续工作。";
  document.querySelector("#quality-models").innerHTML=state.qualityModels.length?state.qualityModels.map(v=>`<article class="card"><div class="card-head"><strong>${esc(v.model_id)}</strong><span class="pill ${['rejected','calibration'].includes(v.status)?'bad':''}">${esc(v.status)}</span></div><p class="mono">${esc(v.system_fingerprint)}<br>${esc(v.prompt_version)}</p>${v.status==='pending_approval'?`<button data-quality-model="${v.endpoint_version_id}" data-action="approve">批准首次接入</button> <button data-quality-model="${v.endpoint_version_id}" data-action="reject">拒绝</button>`:''}</article>`).join(""):"模型首次返回 fingerprint 后会在这里等待人工批准。";
  document.querySelector("#synthetic-candidates").innerHTML=state.synthetic.length?state.synthetic.map(c=>`<article class="card"><div class="card-head"><strong>${esc(c.transformation)}</strong><span class="pill ${c.status==='rejected'?'bad':''}">${esc(c.status)}</span></div><p>${esc(c.task_kind)} · ${esc(short(c.parent_hash))} · ${esc(c.verification_kind)}</p><p class="mono">${esc(c.generation_model_id)} · ${esc(c.generation_system_fingerprint)}</p>${c.status==='quarantined'?`<button data-synthetic="${c.candidate_id}" data-action="approve">人工批准</button> <button data-synthetic="${c.candidate_id}" data-action="reject">拒绝</button>`:''}</article>`).join(""):"暂无合成候选";
  document.querySelector("#draft").innerHTML=build ? `<div class="card"><div class="card-head"><strong>${esc(build.build_id)}</strong><span class="pill">draft</span></div><p>决策 ${build.decision_count} · 回放 ${build.replay_eval_count} · 拒绝 ${build.rejected_record_count}</p><p class="mono">manifest ${esc(build.manifest_hash)}<br>bundle ${esc(build.bundle_hash)}<br>expert view ${esc(build.expert_view_id)}</p></div>` : "尚未构建 Draft";
  document.querySelector("#snapshots").innerHTML=state.snapshots.length ? state.snapshots.map(({snapshot,revocation})=>`<article class="card"><div class="card-head"><strong>${esc(snapshot.snapshot_id)}</strong><span class="pill ${revocation?'bad':''}">${revocation?'revoked':'immutable'}</span></div><p>决策 ${snapshot.decision_count} · 回放 ${snapshot.replay_eval_count} · ${esc(snapshot.created_at)}</p><p class="mono">${esc(snapshot.manifest_hash)}</p></article>`).join("") : "暂无快照";
  const usable=state.snapshots.filter(x=>!x.revocation);
  document.querySelector('[name="snapshot_id"]').innerHTML=usable.map(x=>`<option value="${esc(x.snapshot.snapshot_id)}">${esc(short(x.snapshot.snapshot_id))} · ${x.snapshot.decision_count}/${x.snapshot.replay_eval_count}</option>`).join("");
  const domainExperts=state.taxonomy.experts.filter(x=>!x.is_fallback);
  document.querySelector('[name="expert_ids"]').innerHTML=domainExperts.map(x=>`<option value="${esc(x.id)}" selected>${esc(x.id)} · ${esc(x.description)}</option>`).join("");
  document.querySelector("#expert-views").innerHTML=state.expertViews.length ? state.expertViews.map(view=>`<article class="card"><div class="card-head"><strong>${esc(view.view_id)}</strong><span class="pill ${view.readiness.ready?'':'bad'}">${view.readiness.ready?'training ready':'collecting'}</span></div><p>Router train ${view.readiness.router_train_records}/${view.readiness.minimum_router_records} · ambiguous ${view.ambiguous_count} · OOD ${view.out_of_distribution_count} · negative ${view.negative_transfer_count}</p><p>${Object.entries(view.readiness.per_expert).map(([id,s])=>`${esc(id)} ${s.records.train}/${view.readiness.minimum_train_records_per_expert} + eval replay ${s.evaluation_replay_records}/${view.readiness.minimum_replays_per_expert}`).join(' · ')}</p><p class="mono">taxonomy ${esc(view.taxonomy_hash)}<br>manifest ${esc(view.manifest_hash)}</p></article>`).join("") : "暂无专家视图";
  const disabled=document.querySelector("#training-disabled"), form=document.querySelector("#run-form");
  if(!state.config.enabled){disabled.textContent="AutoDL 未配置：数据集工厂仍会运行，但不能创建 GPU 训练。";disabled.classList.remove("hidden");form.classList.add("hidden");}
  else {disabled.classList.add("hidden");form.classList.remove("hidden");document.querySelector('[name="base_model"]').innerHTML=state.config.base_models.map((m,i)=>`<option value="${i}">${esc(m.model_id)}@${esc(m.revision)}</option>`).join("");document.querySelector('[name="gpu_spec"]').innerHTML=state.config.gpu_allowlist.map(g=>`<option value="${esc(g.id)}">${esc(g.display_name)} · ${g.memory_gb}GB</option>`).join("");}
  document.querySelector("#runs").innerHTML=state.runs.length ? state.runs.map(run=>`<article class="card"><div class="card-head"><strong>${esc(run.run_id)}</strong><span class="pill ${['failed','cancelled','timed_out'].includes(run.status)?'bad':''}">${esc(run.status)}</span></div><p>${run.expert_plan?'Routed LoRA':'Dense LoRA'} · ${esc(run.requested_gpu_spec)} · ¥${run.budget.max_hourly_cny}/h · 总额 ¥${run.budget.max_total_cny} · ${run.budget.max_wall_seconds}s</p><p class="mono">snapshot ${esc(run.snapshot_id)}${run.expert_plan?`<br>experts ${esc(run.expert_plan.expert_ids.join(', '))}`:''}${run.provider_instance_id?`<br>instance ${esc(run.provider_instance_id)}`:""}</p>${run.status==='requested'||run.status==='waiting_capacity'?`<button data-start="${run.run_id}">确认预算并启动</button>`:""}${!['completed','failed','cancelled','timed_out'].includes(run.status)?` <button data-cancel="${run.run_id}">取消</button>`:""}</article>`).join("") : "暂无运行";
  document.querySelector("#expert-adapters").innerHTML=state.adapters.length ? state.adapters.map(adapter=>`<article class="card"><div class="card-head"><strong>${esc(adapter.expert_id)}@${esc(adapter.version)}</strong><span class="pill ${['rejected','rolled_back'].includes(adapter.status)?'bad':''}">${esc(adapter.status)}</span></div><p>${adapter.training_records} records · ${Math.round(adapter.byte_length/1024)} KiB · ${esc(adapter.base_model.model_id)}</p><p class="mono">artifact ${esc(adapter.artifact_hash)}<br>bundle ${esc(adapter.bundle_hash)}</p></article>`).join("") : "暂无适配器候选";
}

function renderEvents(){
  const el=document.querySelector("#events");
  if(!state.events.length){el.classList.add("muted");el.textContent="暂无事件";return;}
  el.classList.remove("muted");
  el.innerHTML=state.events.map(e=>{
    const hot=["emerging","peak"].includes(e.status);
    const items=eventDetail.get(e.event_id);
    const detail=items===undefined?"":items.length?`<div class="card">${items.map(it=>`<p>${esc(it.platform)} · ${safeLink(it.url,it.title)} · 热度 ${esc(it.heat)} · 榜位 ${esc(it.rank)} · ${esc(it.author||"—")} · 观测 ${it.observations.length} 次</p>`).join("")}</div>`:`<p class="muted">暂无条目</p>`;
    return `<article class="card" data-event="${e.event_id}"><div class="card-head"><strong>${esc(e.title)}</strong><span class="pill ${hot?'':'bad'}">${esc(e.status)}</span></div><p>${esc(e.platforms.join(", "))} · 条目 ${e.item_count} · 峰值热度 ${esc(e.peak_heat)} · 最近 ${esc(e.last_seen_at)}</p>${detail}</article>`;
  }).join("");
}
function renderCards(items){
  const el=document.querySelector("#knowledge-cards");
  if(!items.length){el.classList.add("muted");el.textContent="暂无知识卡";return;}
  el.classList.remove("muted");
  el.innerHTML=items.map(({card,score,stale})=>`<article class="card"><div class="card-head"><strong>${esc(card.title)}</strong><span class="pill ${card.status==='retracted'?'bad':''}">${esc(card.status)}</span></div><p>r${card.revision}${score!==undefined?` · 相关度 ${score.toFixed(3)}${stale?" · 已过期":""}`:""} · 有效期至 ${esc(card.valid_until||"—")}</p><p>${esc(card.summary.slice(0,200))}</p></article>`).join("");
}
function renderJobs(){
  const el=document.querySelector("#jobs");
  if(!state.jobs.length){el.classList.add("muted");el.textContent="暂无任务";return;}
  el.classList.remove("muted");
  el.innerHTML=`<table class="jobs"><thead><tr><th>kind</th><th>状态</th><th>尝试</th><th>最近错误</th><th>创建时间</th></tr></thead><tbody>${state.jobs.map(j=>`<tr><td class="mono">${esc(j.kind)}</td><td><span class="pill ${j.status==='dead_letter'?'bad':''}">${esc(j.status)}</span></td><td>${j.attempts}/${j.max_attempts}</td><td>${esc((j.last_error||"").slice(0,120))}</td><td class="mono">${esc(j.created_at)}</td></tr>`).join("")}</tbody></table>`;
}
function renderAcquisition(){
  const topicsEl=document.querySelector("#topics");
  topicsEl.classList.toggle("muted",!state.topics.length);
  topicsEl.innerHTML=state.topics.length?state.topics.map(t=>`<article class="card"><div class="card-head"><strong>${esc(t.name)}</strong><span class="pill ${t.enabled?'':'bad'}">${t.enabled?'enabled':'disabled'}</span></div><p>${esc(t.query)}</p><p>每 ${t.refresh_seconds}s · 关联信息源 ${t.source_policy_ids.length} 个</p></article>`).join(""):"暂无主题";
  const policiesEl=document.querySelector("#source-policies");
  policiesEl.classList.toggle("muted",!state.policies.length);
  policiesEl.innerHTML=state.policies.length?state.policies.map(p=>`<article class="card"><div class="card-head"><strong>${esc(p.name)}</strong><span class="pill ${p.enabled?'':'bad'}">${esc(p.access_mode)} · ${p.enabled?'enabled':'disabled'}</span></div><p>${esc(p.kind)} · <span class="mono">${esc(p.base_url)}</span></p><button data-sync="${p.policy_id}">立即同步</button></article>`).join(""):"暂无信息源";
  renderEvents();
  renderCards(state.cards.map(card=>({card})));
  const documentsEl=document.querySelector("#documents");
  if(!state.documents.length){documentsEl.classList.add("muted");documentsEl.textContent="暂无文档";}
  else {
    documentsEl.classList.remove("muted");
    documentsEl.innerHTML=state.documents.map(d=>`<article class="card"><div class="card-head"><strong>${esc(d.title)}</strong><span class="pill">${esc(d.language)}</span></div><p>${esc(short(d.source_policy_id))} · ${esc(d.published_at||d.fetched_at)} · ${esc(d.content_type)}${d.metadata&&d.metadata.item_count!==undefined?` · 条目 ${esc(d.metadata.item_count)}`:""}</p><button data-read="${esc(d.cleaned_content_hash)}">阅读</button><pre class="doc-pre hidden"></pre></article>`).join("");
  }
  renderJobs();
}
async function reloadEvents(){
  const status=document.querySelector("#event-status").value, platform=document.querySelector("#event-platform").value.trim();
  try{state.events=await api(`/v1/events?limit=100${status!=="all"?`&status=${status}`:""}${platform?`&platform=${encodeURIComponent(platform)}`:""}`);eventDetail.clear();renderEvents();}catch(error){toast(error.message);}
}
document.querySelector("#events-refresh").addEventListener("click",reloadEvents);
document.querySelector("#event-status").addEventListener("change",reloadEvents);
document.querySelector("#event-platform").addEventListener("change",reloadEvents);
document.querySelector("#events").addEventListener("click",async e=>{
  if(e.target.closest("a"))return;
  const card=e.target.closest("[data-event]"); if(!card)return;
  const id=card.dataset.event;
  if(eventDetail.has(id)){eventDetail.delete(id);renderEvents();return;}
  try{const detail=await api(`/v1/events/${id}`);eventDetail.set(id,detail.items||[]);renderEvents();}catch(error){toast(error.message);}
});
document.querySelector("#source-policies").addEventListener("click",async e=>{
  const id=e.target.dataset.sync; if(!id)return;
  e.target.disabled=true;
  try{const result=await api(`/v1/connectors/${id}:sync`,{method:"POST",body:"{}"});toast(`已排入 ${result.job_ids.length} 个 job`);await refresh();}
  catch(error){toast(error.message);e.target.disabled=false;}
});
document.querySelector("#knowledge-search").addEventListener("submit",async e=>{
  e.preventDefault();
  const query=(new FormData(e.currentTarget).get("query")||"").trim();
  if(!query){renderCards(state.cards.map(card=>({card})));return;}
  try{const result=await api("/v1/knowledge:retrieve",{method:"POST",body:JSON.stringify({query,limit:20})});renderCards(result.items);}catch(error){toast(error.message);}
});
document.querySelector("#documents").addEventListener("click",async e=>{
  const hash=e.target.dataset.read; if(!hash)return;
  const pre=e.target.parentElement.querySelector(".doc-pre");
  if(!pre.classList.contains("hidden")){pre.classList.add("hidden");return;}
  try{
    const response=await fetch(`/v1/objects/${hash}`,{headers:{"Accept":"text/plain"},credentials:"same-origin"});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    pre.textContent=await response.text();
    pre.classList.remove("hidden");
  }catch(error){toast(error.message);}
});
document.querySelector("#job-status").addEventListener("change",async()=>{
  const status=document.querySelector("#job-status").value;
  try{state.jobs=await api(`/v1/learning/jobs?limit=100${status!=="all"?`&status=${status}`:""}`);renderJobs();}catch(error){toast(error.message);}
});
document.querySelector("#refresh").addEventListener("click",refresh);
document.querySelector("#quality-backfill").addEventListener("click",async()=>{try{await api("/v1/quality:backfill",{method:"POST",body:JSON.stringify({actor:"admin",reason:"console quality backfill",limit:1000})});toast("已安排质量回填");await refresh();}catch(error){toast(error.message);}});
document.querySelector("#quality-models").addEventListener("click",async e=>{const id=e.target.dataset.qualityModel,action=e.target.dataset.action;if(!id)return;try{await api(`/v1/quality/model-versions/${id}:${action}`,{method:"POST",body:JSON.stringify({actor:"admin",reason:"console fingerprint review"})});toast(`模型 fingerprint 已${action==='approve'?'批准':'拒绝'}`);await refresh();}catch(error){toast(error.message);}});
document.querySelector("#synthetic-candidates").addEventListener("click",async e=>{const id=e.target.dataset.synthetic,action=e.target.dataset.action;if(!id)return;try{await api(`/v1/synthetic-candidates/${id}:${action}`,{method:"POST",body:JSON.stringify({actor:"admin",reason:"console synthetic review"})});toast(`合成候选已${action==='approve'?'批准':'拒绝'}`);await refresh();}catch(error){toast(error.message);}});
document.querySelector("#build-form").addEventListener("submit",async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await api(`/v1/datasets/${kind}:build`,{method:"POST",body:JSON.stringify(Object.fromEntries(f))});toast(state.quality?.enabled?"Build 已生成，等待 Pro 审计后才移动 Draft":"Draft 已构建");await refresh();}catch(error){toast(error.message);}});
document.querySelector("#snapshot-form").addEventListener("submit",async e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget));try{await api("/v1/dataset-snapshots",{method:"POST",body:JSON.stringify({kind,build_id:null,...f})});toast("Snapshot 已冻结");await refresh();}catch(error){toast(error.message);}});
document.querySelector("#run-form").addEventListener("submit",async e=>{
  e.preventDefault();
  const data=new FormData(e.currentTarget),f=Object.fromEntries(data);
  const model=state.config.base_models[Number(f.base_model)];
  const snapshot=state.snapshots.find(x=>x.snapshot.snapshot_id===f.snapshot_id)?.snapshot;
  const expertIds=data.getAll("expert_ids"),trainRouter=data.has("train_router"),trainShared=data.has("train_shared");
  let expert_plan=null;
  if(f.architecture==="routed_lora"){
    const view=state.expertViews.find(x=>x.view_id===snapshot?.expert_view_id);
    if(!view)return toast("Snapshot 没有绑定专家数据视图");
    const readiness=view.readiness,reasons=[];
    if(trainRouter&&readiness.router_train_records<readiness.minimum_router_records)reasons.push(`router ${readiness.router_train_records}/${readiness.minimum_router_records}`);
    for(const id of expertIds){const stats=readiness.per_expert[id];if(!stats||stats.records.train<readiness.minimum_train_records_per_expert||stats.evaluation_replay_records<readiness.minimum_replays_per_expert)reasons.push(`${id} 未达到 train/独立 replay 门槛`);}
    if(!trainRouter&&!trainShared&&!expertIds.length)reasons.push("至少选择一个待训练适配器");
    if(reasons.length)return toast(`专家数据尚未达到训练门槛：${reasons.join('; ')}`);
    expert_plan={architecture:"routed_lora",expert_view_id:view.view_id,train_router:trainRouter,train_shared:trainShared,expert_ids:expertIds,router_top_k:1,fallback_expert_id:state.taxonomy.fallback_expert_id};
  }
  try{
    await api("/v1/training-runs",{method:"POST",body:JSON.stringify({snapshot_id:f.snapshot_id,base_model:model,qlora:{epochs:1,max_sequence_length:2048,lora_rank:16,lora_alpha:32,lora_dropout:.05,learning_rate:.0002,gradient_accumulation_steps:16},expert_plan,gpu_spec:f.gpu_spec,administrator:f.administrator,reason:f.reason,budget:{max_hourly_cny:Number(f.max_hourly_cny),max_total_cny:Number(f.max_total_cny),max_wall_seconds:Number(f.max_wall_seconds)}})});
    toast("TrainingRun 已创建；尚未调用 GPU");await refresh();
  }catch(error){toast(error.message);}
});
document.querySelector("#runs").addEventListener("click",async e=>{const start=e.target.dataset.start,cancel=e.target.dataset.cancel;try{if(start){const run=state.runs.find(x=>x.run_id===start);if(!confirm(`即将创建 AutoDL 实例\nGPU: ${run.requested_gpu_spec}\n上限: ¥${run.budget.max_hourly_cny}/h\n总预算: ¥${run.budget.max_total_cny}\n最长: ${run.budget.max_wall_seconds}s`))return;await api(`/v1/training-runs/${start}:start`,{method:"POST",body:JSON.stringify({administrator:"admin",reason:"console budget confirmation",confirm_gpu_spec:run.requested_gpu_spec,confirm_max_hourly_cny:run.budget.max_hourly_cny,confirm_max_total_cny:run.budget.max_total_cny,confirm_max_wall_seconds:run.budget.max_wall_seconds})});toast("已请求 AutoDL 实例");}if(cancel){await api(`/v1/training-runs/${cancel}:cancel`,{method:"POST",body:JSON.stringify({administrator:"admin",reason:"cancelled from console"})});toast("已取消并请求释放 GPU");}await refresh();}catch(error){toast(error.message);}});
refresh();
