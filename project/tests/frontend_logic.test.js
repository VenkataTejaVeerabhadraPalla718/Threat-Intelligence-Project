const fs=require('fs'),vm=require('vm');
const src=fs.readFileSync(require('path').join(__dirname,'..','frontend','js','app.js'),'utf8');
const els={};
function fake(id){return els[id]||(els[id]=new Proxy({classList:{add(){},remove(){},toggle(){}},style:{},dataset:{},_html:'',
  set innerHTML(v){this._html=v},get innerHTML(){return this._html},addEventListener(){},querySelector(){return fake('child')},
  querySelectorAll(){return []},insertAdjacentHTML(){},append(){},remove(){},focus(){}},{get:(t,k)=>k in t?t[k]:undefined,set:(t,k,v)=>{t[k]=v;return true}}))}
const store={};
const ctx={console,URLSearchParams,Date,JSON,Object,Array,String,Number,Promise,setTimeout,Headers:class{set(){}},
 document:{querySelector:s=>fake(s),querySelectorAll:()=>[],addEventListener(){},documentElement:{dataset:{}},body:{classList:{add(){},remove(){},toggle(){},contains:()=>false},append(){}},createElement:()=>fake('new')},
 localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v,removeItem:k=>delete store[k]},
 sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},
 location:{pathname:'/login',search:'',href:''},history:{replaceState(){},pushState(){}},addEventListener(){},innerWidth:1400,fetch:async()=>({ok:true,json:async()=>({})}),Chart:undefined,navigator:{}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(src+';this.__t={esc,rich,fmt,fdate,parseDate,qs,pager,sevPill,kpi}',ctx);
const t=ctx.__t,ok=(c,m)=>{console.log((c?'PASS ':'FAIL ')+m);if(!c)process.exitCode=1};
ok(t.esc('<img src=x onerror=alert(1)>')==='&lt;img src=x onerror=alert(1)&gt;','esc neutralises tags');
ok(!t.rich('<script>alert(1)</script>').includes('<script>'),'rich() escapes raw HTML');
const r=t.rich('Run:\n```bash\ndocker compose ps <x>\n```\nuse `mongosh`');
ok(r.includes('class="codeblock"')&&r.includes('data-copy')&&r.includes('&lt;x&gt;')&&r.includes('<code>mongosh</code>'),'code fence -> copyable block, content escaped, inline code');
ok(t.qs({a:'1',b:'',c:null,d:'x y'})==='a=1&d=x+y','qs drops empty values');
ok(t.parseDate('2026-11-14T10:00:00').toISOString()==='2026-11-14T10:00:00.000Z','naive Mongo timestamp treated as UTC');
ok(t.fdate(null)==='—','fdate null');
ok(t.pager(0,0,25).includes('No results')&&t.pager(100,0,25).includes('1–25 of 100'),'pager text');
ok(t.pager(100,75,25).match(/data-page="next"[^>]*disabled/),'pager disables Next on last page');
const login=els['#authRoot']._html;
ok(login.includes('Sign in')&&login.includes('type="password"')&&login.includes('showpw'),'login card renders with show/hide');
ok(!/SENTINEL|SX|feature|threat|platform/i.test(login),'login page contains NO project name / marketing text');
ok(!login.includes('aside'),'no left-side info container');
