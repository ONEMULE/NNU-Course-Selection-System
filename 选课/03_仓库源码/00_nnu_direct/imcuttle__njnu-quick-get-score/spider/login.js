/**
 * Created by Yc on 2016/6/30.
 */
var options = require('./options');
var queryString = require('querystring');
// var net = require('net');
var http = require('http');
var u = require('../utils/index');
var iconv = require('iconv-lite');

var h = require('fs').readFileSync('headers/logon.txt').toString();
/*
 var st = net.createConnection(80,'223.2.10.25');
 var body = queryString.stringify(data);
 st.write(h+`Content-Length: ${body.length}\r\nCookie: JSESSIONID=${id}.kingo154\r\n\r\n${body}`);
 st.end();
 return st;
 */

var option = u.extend(options,{
    headers:{
        "Content-Type": "application/x-www-form-urlencoded"
    },
    path:'/cas/logon.action',
    method:'POST'
});

module.exports = function (data,id,callback) {
    option.headers['Cookie'] = `JSESSIONID=${id}.kingo154`;
    http.request(option,callback).end(queryString.stringify(data));
}
