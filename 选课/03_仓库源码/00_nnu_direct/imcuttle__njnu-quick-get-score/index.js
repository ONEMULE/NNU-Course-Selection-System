/**
 * Created by Yc on 2016/6/30.
 */

var http = require('http'),
    fs = require('fs'),
    Transform = require('stream').Transform;
var options = require('./spider/options');
var login = require('./spider/login');
var lookup = require('./spider/data');
var ranNum = require('./server/ranNumber');
var u = require('./utils/index');
var url = require('url');
var md5 = require('./utils/md5');
var recognize = require('./server/javaServices');


var sessions = {};
http.createServer((req,res)=>{
    var cookie = u.parseCookie(req.headers.cookie);
    if(!cookie['connect.id']){
        res.setHeader('Set-Cookie',[`connect.id=${md5.hex_md5(''+Date.now())}`])
    }
    if(req.url.startsWith('/ranNumber')){
        var ops = u.extend(options,{path:'/cas/genValidateCode'});
        ranNum(cookie['connect.id'],(numres)=>{
            var time = cookie['connect.id'];
            //     name = "VerifyCode/data/"+time+".jpeg";
            // var file = fs.createWriteStream(name);
            // numres.on('data',function (chs) {
            //     file.write(chs);
            // });
            // numres.on('end',()=>{
            //     file.end();
            // });
            sessions[time] = [];
            numres.on('data',(data)=>{sessions[time].push(data);});
            numres.pipe(res);
        })
    }else if(req.url.startsWith('/ajax')){
        var arg = url.parse(req.url, true).query;
        if(arg.act=='login'){
            delete arg.act;
            // console.log(arg.username);
            login(arg,cookie['connect.id'],(st)=>{
                st.pipe(res);
            });
        }else if(arg.act=='lookup'){
            delete arg.act;
            lookup(arg.result,cookie['connect.id'],(err,data)=>{
                if(err) {
                    console.error(err);
                    res.end(JSON.stringify({code:500,message:'出错'}));
                }
                else
                    res.end(data);
            })
        }else if(arg.act=='recognize') {
            delete arg.act;
            var req = recognize((income)=>{
                income.pipe(res);
            });
            req.end(Buffer.concat(sessions[cookie['connect.id']]));
            // recognize(cookie['connect.id']+".jpeg",(outstr,errstr)=>{
            //     res.end(outstr);
            // })
        }
    }else
        fs.readFile(__dirname+'/static/'+(req.url==='/'?'index.html':req.url),
            function (err,data) {
                if(err){
                    res.writeHead(500);
                    return res.end('Error loading');
                }
                res.writeHead(200);
                res.end(data);
            }
        );
}).listen(3010);

console.info("http://localhost:3010");
// login()