/**
 * Created by Yc on 2016/6/30.
 */

module.exports = {
    extend : function (src) {
        var out = {};
        var others = [].slice.call(arguments);
        others.forEach(x=>{
            for(var k in x){
                if(x.hasOwnProperty(k))
                    out[k] = x[k];
            }
        })
        return out;
    },
    parseCookie : function(cookie){
        var cookies = {};
        if (!cookie) return cookies;
        var list = cookie.split(";");
        for (var i = 0; i < list.length; i++) {
            var pair = list[i].split("=");
            cookies[pair[0].trim()] = pair[1];
        }
        return cookies;
    },

}
Date.prototype.Format = function (fmt) { //author: meizz
    var o = {
        "M+": this.getMonth() + 1, //月份
        "d+": this.getDate(), //日
        "h+": this.getHours(), //小时
        "m+": this.getMinutes(), //分
        "s+": this.getSeconds(), //秒
        "q+": Math.floor((this.getMonth() + 3) / 3), //季度
        "S": this.getMilliseconds() //毫秒
    };
    if (/(y+)/.test(fmt)) fmt = fmt.replace(RegExp.$1, (this.getFullYear() + "").substr(4 - RegExp.$1.length));
    for (var k in o)
        if (new RegExp("(" + k + ")").test(fmt)) fmt = fmt.replace(RegExp.$1, (RegExp.$1.length == 1) ? (o[k]) : (("00" + o[k]).substr(("" + o[k]).length)));
    return fmt;
}