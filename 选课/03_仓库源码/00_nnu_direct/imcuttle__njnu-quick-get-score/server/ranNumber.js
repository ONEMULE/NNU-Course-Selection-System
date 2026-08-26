/**
 * Created by Yc on 2016/6/30.
 */
var options = require('../spider/options');

var http = require('http');
var u = require('../utils/index');

options = u.extend(options,{headers:{},path:'/cas/genValidateCode'})

module.exports = function (id,callback) {
    options.headers.Cookie = `JSESSIONID=${id}.kingo154`;
    var req = http.request(options, callback);
    req.on('error', (e) => {
        console.log(`problem with request: ${e.message}`);
    });
    req.end();
}