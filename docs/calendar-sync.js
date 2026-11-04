const weekdays=["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
const calKey="scooterCalendarV1";
let calendar=[];
try{const x=JSON.parse(localStorage.getItem(calKey)||"[]");if(Array.isArray(x))calendar=x}catch(e){}
let editingTrip=null,sessionToken=null,syncTimer=null;
function renderCalendarSelectors(){
 const fav=$("calFavorite"),selected=fav.value;
 fav.replaceChildren();
 const empty=document.createElement("option");empty.value="";empty.textContent="Scegli un percorso salvato…";fav.append(empty);
 favorites.forEach((route,i)=>{if(!regions[route.from]||!regions[route.to])return;const o=document.createElement("option");o.value=String(i);o.textContent=route.from+" → "+route.to;fav.append(o)});
 if(selected&&[...fav.options].some(o=>o.value===selected))fav.value=selected;

 for(const id of ["calFrom","calTo"]){
  const el=$(id),old=el.value;el.replaceChildren();
  Object.keys(regions).forEach(k=>{const o=document.createElement("option");o.value=k;o.textContent=k;el.append(o)});
  el.value=regions[old]?old:id==="calFrom"?"casa":"fisica";
 }
}
$("calFavorite").onchange=()=>{
 const item=favorites[Number($("calFavorite").value)];
 if($("calFavorite").value!==""&&item){$("calFrom").value=item.from;$("calTo").value=item.to}
};
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
    editingTrip=t.id;renderCalendarSelectors();$("calDay").value=t.day;$("calTime").value=t.time;$("calFrom").value=t.from;$("calTo").value=t.to;$("calFavorite").value="";
    $("calDialogTitle").textContent="✏️ Modifica tragitto";$("calSave").textContent="Salva modifica";$("calDialog").showModal();
   };
   const remove=document.createElement("button");remove.textContent="×";remove.title="Elimina";remove.onclick=()=>{calendar=calendar.filter(x=>x.id!==t.id);persistCalendar()};
   card.append(edit,remove);col.append(card);
  });root.append(col);
 });
}
function resetEdit(){editingTrip=null;$("calSave").textContent="Salva tragitto";$("calDialogTitle").textContent="➕ Aggiungi tragitto";$("calDialog").close()}
$("calOpen").onclick=()=>{
 editingTrip=null;renderCalendarSelectors();$("calFavorite").value="";
 $("calDay").value=(new Date().getDay()+6)%7;$("calTime").value="09:00";
 $("calDialogTitle").textContent="➕ Aggiungi tragitto";$("calSave").textContent="Salva tragitto";$("calDialog").showModal();
};
$("calCancel").onclick=resetEdit;
$("calDialog").addEventListener("close",()=>{editingTrip=null});
$("calSave").onclick=()=>{
 const trip={id:editingTrip||crypto.randomUUID(),day:Number($("calDay").value),time:$("calTime").value,from:$("calFrom").value,to:$("calTo").value};
 if(!trip.time||!regions[trip.from]||!regions[trip.to]){alert("Completa i campi del tragitto");return}
 if(editingTrip)calendar=calendar.map(t=>t.id===editingTrip?trip:t);else calendar.push(trip);
 persistCalendar();resetEdit();
};
renderCalendarSelectors();
renderCalendar();

const apiFile="https://api.github.com/repos/giacomoubaldi/meteo-scooter-bologna/contents/data/config.json";
let remoteSha=null,dirty=false,loadingRemote=false;
function queueSync(){if(!loadingRemote){dirty=true;$("syncStatus").textContent="Modifiche da salvare: premi Commit and Reload."}}
function b64Encode(value){return btoa(Array.from(new TextEncoder().encode(value),b=>String.fromCharCode(b)).join(""))}
function b64Decode(value){return new TextDecoder().decode(Uint8Array.from(atob(value.replace(/\s/g,"")),c=>c.charCodeAt(0)))}
async function getConfig(){
 const r=await fetch(apiFile+"?nocache="+Date.now(),{cache:"no-store"});
 if(!r.ok)throw Error("Lettura GitHub: HTTP "+r.status);
 const file=await r.json();
 return {sha:file.sha,data:JSON.parse(b64Decode(file.content))};
}
function applyConfig(data){
 loadingRemote=true;
 regions={...defaults,...(data.tappe||{})};
 favorites=Array.isArray(data.favorites)?data.favorites:[];
 calendar=Array.isArray(data.calendar)?data.calendar:[];
 localStorage.setItem("regionsScooter",JSON.stringify(regions));
 localStorage.setItem(favoritesKey,JSON.stringify(favorites));
 localStorage.setItem(calKey,JSON.stringify(calendar));
 render();renderFavorites();renderCalendarSelectors();renderCalendar();
 loadingRemote=false;dirty=false;
}
async function loadConfig(){
 try{const {sha,data}=await getConfig();remoteSha=sha;applyConfig(data);$("syncStatus").textContent="Dati caricati da GitHub."}
 catch(e){$("syncStatus").textContent="Caricamento non riuscito: "+e.message}
}
$("commitReload").onclick=()=>{$("tokenError").textContent="";$("tokenDialog").showModal();$("githubToken").focus()};
$("tokenCancel").onclick=()=>{$("tokenDialog").close();$("githubToken").value=""};
$("tokenForm").addEventListener("submit",async event=>{
 event.preventDefault();
 const token=$("githubToken").value.trim();
 if(!token)return;
 const button=$("tokenSubmit");button.disabled=true;
 $("tokenError").textContent="";
 try{
  const latest=await getConfig();
  if(latest.sha!==remoteSha)throw Error("I dati sono cambiati su un altro dispositivo. Ricarica prima di salvare.");
  const payload={tappe:regions,favorites,calendar};
  const r=await fetch(apiFile,{method:"PUT",headers:{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","Content-Type":"application/json"},body:JSON.stringify({message:"Update scooter calendar, stops and favorites",content:b64Encode(JSON.stringify(payload,null,2)),sha:latest.sha,branch:"main"})});
  if(!r.ok)throw Error("Commit non riuscito: HTTP "+r.status);
  $("syncStatus").textContent="Commit completato. Ricaricamento…";
  $("tokenDialog").close();
  $("githubToken").value="";
  location.reload();
 }catch(e){$("tokenError").textContent=e.message}
 finally{button.disabled=false}
});

loadConfig();
