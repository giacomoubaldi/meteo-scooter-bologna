const weekdays=["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
const calKey="scooterCalendarV1";
let calendar=[];
try{const x=JSON.parse(localStorage.getItem(calKey)||"[]");if(Array.isArray(x))calendar=x}catch(e){}
let editingTrip=null,sessionToken=null,syncTimer=null;
function renderCalendarSelectors(){
 for(const id of ["calFrom","calTo"]){
  const el=$(id),old=el.value;el.replaceChildren();
  Object.keys(regions).forEach(k=>{const o=document.createElement("option");o.value=k;o.textContent=k;el.append(o)});
  el.value=regions[old]?old:id==="calFrom"?"casa":"fisica";
 }
}
weekdays.forEach((name,i)=>{const o=document.createElement("option");o.value=i;o.textContent=name;$("calDay").append(o)});
function persistCalendar(){localStorage.setItem(calKey,JSON.stringify(calendar));renderCalendar();queueSync()}
function renderCalendar(){
 const root=$("calendar");root.replaceChildren();
 weekdays.forEach((day,i)=>{
  const col=document.createElement("div");col.className="calendar-day";
  const title=document.createElement("h4");title.textContent=day;col.append(title);
  calendar.filter(t=>t.day===i).sort((a,b)=>a.time.localeCompare(b.time)).forEach(t=>{
   const card=document.createElement("div");card.className="calendar-trip";
   const label=document.createElement("div");label.textContent=t.time+" · "+t.from+" → "+t.to;card.append(label);
   const edit=document.createElement("button");edit.textContent="✏️";edit.title="Modifica";edit.onclick=()=>{
    editingTrip=t.id;$("calDay").value=t.day;$("calTime").value=t.time;$("calFrom").value=t.from;$("calTo").value=t.to;
    $("calSave").textContent="Salva modifica";$("calCancel").hidden=false;
   };
   const remove=document.createElement("button");remove.textContent="×";remove.title="Elimina";remove.onclick=()=>{calendar=calendar.filter(x=>x.id!==t.id);persistCalendar()};
   card.append(edit,remove);col.append(card);
  });root.append(col);
 });
}
function resetEdit(){editingTrip=null;$("calSave").textContent="Aggiungi tragitto";$("calCancel").hidden=true}
$("calCancel").onclick=resetEdit;
$("calSave").onclick=()=>{
 const trip={id:editingTrip||crypto.randomUUID(),day:Number($("calDay").value),time:$("calTime").value,from:$("calFrom").value,to:$("calTo").value};
 if(!trip.time||!regions[trip.from]||!regions[trip.to]){alert("Completa i campi del tragitto");return}
 if(editingTrip)calendar=calendar.map(t=>t.id===editingTrip?trip:t);else calendar.push(trip);
 resetEdit();persistCalendar();
};
renderCalendar();
const syncUrl=window.SCOOTER_SUPABASE_URL?.replace(/\/$/,""),syncKey=window.SCOOTER_SUPABASE_ANON_KEY;
const configured=Boolean(syncUrl&&syncKey);
const status=msg=>$("syncStatus").textContent=msg;
if(configured)status("Accedi per sincronizzare i dati.");
async function sb(path,method="GET",body=null,token=syncKey){
 const response=await fetch(syncUrl+path,{method,headers:{"apikey":syncKey,"Authorization":"Bearer "+token,"Content-Type":"application/json",...(method==="POST"?{"Prefer":"resolution=merge-duplicates,return=minimal"}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const data=await response.json().catch(()=>null);
 if(!response.ok)throw Error(data?.msg||data?.message||data?.error_description||"Errore database "+response.status);
 return data;
}
let currentUser=null;
async function loadCloud(){
 const data=await sb("/rest/v1/scooter_settings?select=payload&user_id=eq."+encodeURIComponent(currentUser), "GET",null,sessionToken);
 if(data.length){
  const payload=data[0].payload;
  if(payload?.regions&&typeof payload.regions==="object")regions={...defaults,...payload.regions};
  if(Array.isArray(payload?.favorites))favorites=payload.favorites;
  if(Array.isArray(payload?.calendar))calendar=payload.calendar;
  localStorage.setItem("regionsScooter",JSON.stringify(regions));
  localStorage.setItem(favoritesKey,JSON.stringify(favorites));
  localStorage.setItem(calKey,JSON.stringify(calendar));
  render();renderFavorites();renderCalendar();
 }else await uploadCloud();
}
async function uploadCloud(){
 if(!currentUser||!sessionToken)return;
 await sb("/rest/v1/scooter_settings?on_conflict=user_id","POST",{user_id:currentUser,payload:{regions,favorites,calendar}},sessionToken);
 status("☁️ Dati sincronizzati.");
}
function queueSync(){
 if(!currentUser)return;
 status("Sincronizzazione in corso…");
 clearTimeout(syncTimer);syncTimer=setTimeout(()=>uploadCloud().catch(e=>status("Errore sincronizzazione: "+e.message)),600);
}
$("syncLogin").onclick=async()=>{
 if(!configured){status("Configura Supabase in sync-config.js.");return}
 try{
  const data=await sb("/auth/v1/token?grant_type=password","POST",{email:$("syncEmail").value,password:$("syncPassword").value});
  sessionToken=data.access_token;currentUser=data.user.id;
  $("syncPassword").value="";
  await loadCloud();
  $("syncLogout").hidden=false;status("☁️ Account collegato. Modifiche sincronizzate.");
 }catch(e){status("Accesso non riuscito: "+e.message)}
};
$("syncLogout").onclick=()=>{sessionToken=null;currentUser=null;$("syncLogout").hidden=true;status("Disconnesso.")};
