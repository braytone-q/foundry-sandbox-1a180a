"use strict";
function captureDeviceLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) { reject(new Error("Device location is required. Use a browser that supports location on localhost or HTTPS.")); return; }
    let settled = false;
    const fail = message => { if (settled) return; settled = true; clearTimeout(deadline); reject(new Error(message)); };
    const deadline = setTimeout(() => fail("Location is required before submission. Allow location access and try again."), 20000);
    try {
      navigator.geolocation.getCurrentPosition(position => {
        if (settled) return;
        const {latitude, longitude, accuracy} = position.coords;
        const age = Date.now() - position.timestamp;
        if (![latitude, longitude, accuracy, position.timestamp].every(Number.isFinite) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180 || accuracy < 0 || age > 300000 || age < -30000) {
          fail("The device returned an invalid or stale location. Enable location services and try again."); return;
        }
        settled = true; clearTimeout(deadline);
        resolve({latitude, longitude, accuracy_m: accuracy, captured_at: new Date(position.timestamp).toISOString(), source: "browser_geolocation"});
      }, error => fail(error.code === 1 ? "Location permission is required. Allow this site to access your location, then try again." :
        error.code === 3 ? "Location capture timed out. Check device location services and try again." :
        "Device location is unavailable. Enable location services and try again."),
        {enableHighAccuracy: true, maximumAge: 0, timeout: 15000});
    } catch { fail("Device location could not be obtained. Check browser permissions and try again."); }
  });
}
