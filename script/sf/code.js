window = global;

navigator = {}
navigator.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
location = {
    "ancestorOrigins": {},
    "href": "https://y.qq.com/n/ryqq/toplist/4",
    "origin": "https://y.qq.com",
    "protocol": "https:",
    "host": "y.qq.com",
    "hostname": "y.qq.com",
    "port": "",
    "pathname": "/n/ryqq/toplist/4",
    "search": "",
    "hash": ""
}
proxy_array = ['window', 'document', 'location', 'navigator', 'history','screen' ]



N = /[\uD800-\uDBFF][\uDC00-\uDFFFF]|[^\x00-\x7F]/g;
const B = (t) => Buffer.from(t, "utf8").toString("base64");


V = (t, e=!1) => e ? (t => t.replace(/=/g, "").replace(/[+\/]/g, (t => "+" == t ? "-" : "_")))(B(t)) : B(t);

var M = {
            randomUUID: "undefined" != typeof crypto && crypto.randomUUID && crypto.randomUUID.bind(crypto)
        };

function O(t, e, r) {
            if (M.randomUUID && !e && !t)
                return M.randomUUID();
            const n = (t = t || {}).random || (t.rng || C)();
            if (n[6] = 15 & n[6] | 64,
            n[8] = 63 & n[8] | 128,
            e) {
                r = r || 0;
                for (let t = 0; t < 16; ++t)
                    e[r + t] = n[t];
                return e
            }
            return function(t, e=0) {
                return (T[t[e + 0]] + T[t[e + 1]] + T[t[e + 2]] + T[t[e + 3]] + "-" + T[t[e + 4]] + T[t[e + 5]] + "-" + T[t[e + 6]] + T[t[e + 7]] + "-" + T[t[e + 8]] + T[t[e + 9]] + "-" + T[t[e + 10]] + T[t[e + 11]] + T[t[e + 12]] + T[t[e + 13]] + T[t[e + 14]] + T[t[e + 15]]).toLowerCase()
            }(n)
        }

function ft(t, e) {
    var r = O()
      , n = String(V(r))
      , i = String(V(O()))
      , o = String(V(t))
      , a = String(V("web"))
      , s = String(V((null === location || void 0 === location ? void 0 : location.pathname) || ""))
      , c = String(V(e));
    return {
        code: "".concat(1, "-").concat(n, "-").concat(i, "-").concat(0, "-").concat(o, "-").concat(a, "-").concat(s, "-").concat(c),
        traceId: r
    }
}
var key = "fb40817085be4e398e0b6f4b08177746"
function get_sw8(url_path) {
    return ft(key, url_path)
}

console.log(ft("fb40817085be4e398e0b6f4b08177746","/mcs-mimp/commonPost/~memberEs~taskRecord~finishTask"))