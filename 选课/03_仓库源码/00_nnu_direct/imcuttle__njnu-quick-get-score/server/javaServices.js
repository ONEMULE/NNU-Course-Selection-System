/**
 * Created by Moyu on 16/7/25.
 */
var http = require("http");
var queryString = require('querystring');


module.exports = function (cb) {
    var stream = http.request({
        method: 'POST',
        hostname: "localhost",
        port: 7777,
        path: '/imageRecognize/data'
    },function (res) {
        cb(res);
    });
    return stream;
};
