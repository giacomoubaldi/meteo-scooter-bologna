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

const apiFile="https://api.github.com/repos/giacomoubaldi/meteo-scooter-bologna/contents/data/config.json";
let remoteSha=null,dirty=false,loadingRemote=false;
function queueSync(){if(!loadingRemote){dirty=true;$("syncStatus").textContent="Modifiche da salvare: premi Commit and Reload."}}
function b64Encode(value){return btoa(Array.from(new TextEncoder().encode(value),b=>String.fromCharCode(b)).join(""))}
function b64Decode(value){return new TextDecoder().decode(Uint8Array.from(atob(value.replace(/\\s/g,"")),c=>c.charCodeAt(0)))}
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
 render();renderFavorites();renderCalendar();
 loadingRemote=false;dirty=false;
}
async function loadConfig(){
 try{const {sha,data}=await getConfig();remoteSha=sha;applyConfig(data);$("syncStatus").textContent="Dati caricati da GitHub."}
 catch(e){$("syncStatus").textContent="Caricamento non riuscito: "+e.message}
}
$("commitReload").onclick=async()=>{
 const token=$("githubToken").value.trim();
 if(!token){$("syncStatus").textContent="Inserisci il token GitHub per salvare.";return}
 const button=$("commitReload");button.disabled=true;
 try{
  const latest=await getConfig();
  if(latest.sha!==remoteSha)throw Error("Modifiche effettuate da un altro dispositivo: ricarica la pagina prima di salvare.");
  const payload={tappe:regions,favorites,calendar};
  const r=await fetch(apiFile,{method:"PUT",headers:{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","Content-Type":"application/json"},body:JSON.stringify({message:"Update scooter calendar, stops and favorites",content:b64Encode(JSON.stringify(payload,null,2)),sha:latest.sha,branch:"main"})});
  if(!r.ok)throw Error("Commit non riuscito: HTTP "+r.status);
  $("githubToken").value="";
  location.reload();
 }catch(e){$("syncStatus").textContent=e.message;button.disabled=false}
};
loadConfig();
