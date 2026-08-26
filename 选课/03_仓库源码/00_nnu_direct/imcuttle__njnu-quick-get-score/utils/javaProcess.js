/**
 * Created by Moyu on 16/7/24.
 */

var cp = require('child_process');


module.exports = function (srcfile, cb) {
    cp.exec("cd VerifyCode && java moyu.VerifyCode data/"+srcfile,(error, stdout, stderr) => {
        if (error) {
            cb("出错啦");
            console.error(`exec error: ${error}`);
            return;
        }
        console.log(`stdout: ${stdout}`);
        console.log(`stderr: ${stderr}`);
        cb(stdout,stderr);
    });
};

