const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({navigator:{},Date,Promise,Error,setTimeout,clearTimeout,console});
vm.runInContext(fs.readFileSync('regen_api/static/location.js','utf8'),context);
const run=code=>vm.runInContext(code,context);
async function checks(){
 let options;
 context.navigator.geolocation={getCurrentPosition(success,error,opts){options=opts;success({timestamp:Date.now(),coords:{latitude:0.1,longitude:36.2,accuracy:8}});}};
 const fix=await run('captureDeviceLocation()');
 assert.equal(fix.latitude,0.1);assert.equal(fix.longitude,36.2);assert.equal(fix.accuracy_m,8);
 assert.equal(fix.source,'browser_geolocation');assert.ok(Math.abs(Date.parse(fix.captured_at)-Date.now())<2000);
 assert.equal(options.maximumAge,0);assert.equal(options.enableHighAccuracy,true);assert.equal(options.timeout,15000);
 for(const code of [1,2,3]){
  context.navigator.geolocation={getCurrentPosition(success,error){error({code});}};
  await assert.rejects(run('captureDeviceLocation()'));
 }
 context.navigator.geolocation=undefined;await assert.rejects(run('captureDeviceLocation()'));
 // Bound a permission prompt that never responds without sleeping for 20 seconds.
 let deadline,deadlineMs,lateSuccess;
 context.setTimeout=(fn,ms)=>{deadline=fn;deadlineMs=ms;return 1;};context.clearTimeout=()=>{};
 context.navigator.geolocation={getCurrentPosition(success){lateSuccess=success;}};
 const waiting=run('captureDeviceLocation()');assert.equal(deadlineMs,20000);deadline();await assert.rejects(waiting);
 lateSuccess({timestamp:Date.now(),coords:{latitude:1,longitude:2,accuracy:5}});
 console.log('PASS fresh location, denial, unavailable location and pending permission deadline');
}
checks().catch(e=>{console.error(e);process.exitCode=1;});
