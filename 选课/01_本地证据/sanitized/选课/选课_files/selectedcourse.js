/**
 * 初始化系统参数标题（设置页面学年学期、周次、校区信息）
 */
;
(function(_mode) {

    _mode.titleInit = function($dom) {
        titleInit($dom);
    };

    function titleInit($dom) {
        // 当前选课的学年，学期，周次
    	var xklc = JSON.parse(sessionStorage.getItem('currentBatch'));
        // 学年学期名称
        var schoolTermName = xklc.schoolTermName;
        // 周次范围
        var weekRange = xklc.weekRange;
        var html = schoolTermName + "&nbsp;" + weekRange;
        // 当前校区
        var currentCampus = JSON.parse(sessionStorage.getItem('currentCampus'));
        var teachingClassType = sessionStorage.getItem('teachingClassType');
        if (teachingClassType != 'QXKC' && currentCampus != null) {
            html += '<span style="margin-left: 8px;">' + currentCampus.name + '<span>' +
            		'<span class="home-change-campus" style="margin-left: 4px;color: #047ADC;cursor: pointer;">切换<span>';
        }
        $dom.html(html);
    }
})(window.CVTitleMode = window.CVTitleMode || {});

/**
 * 页脚信息
 */
;
(function(_mode) {

    _mode.init = function() {
        setCelebrityFamous();
    };

    function setCelebrityFamous() {
        var dataList = JSON.parse(sessionStorage.getItem('celebrityFamous'));
        if (dataList != null && dataList.length > 0) {
            initFooterMessage(dataList[randomNumBoth(0, dataList.length - 1)]);
        } else {
            queryCelebrityFamous().done(function(resp) {
                var code = resp.code;
                if (code != null && code == '1') {
                    var dataList = resp.dataList;
                    if (dataList != null && dataList.length > 0) {
                        var randomIndex = randomNumBoth(0, dataList.length - 1);
                        initFooterMessage(dataList[randomIndex]);
                    }
                }
            });
        }
        // 设置页脚固定在页面底部
        setContentMinHeight($('.main').children('article'));
    };

    /**
     * 设置页面数据
     */
    function initFooterMessage(_data) {
        $("#ecDiv").html(_data.englishContent);
        $("#cDiv").html(_data.content);
        $("#authorDiv").html(_data.author);
    };

    /**
     * 数字区间取随机数
     */
    function randomNumBoth(Min, Max) {
        var Range = Max - Min;
        var Rand = Math.random();
        //四舍五入
        var num = Min + Math.round(Rand * Range);
        return num;
    };
})(window.CVFotterMessage = window.CVFotterMessage || {});

/**
 * 选课结果
 */
;
(function(_course) {

    _course.init = function() {
        initCourseResultList();
    };

    function initCourseResultList() {
        var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
        var studentCode = studentInfo.code; // 学号
        var queryParam = {
            'studentCode': studentCode,
            'electiveBatchCode':studentInfo.electiveBatch.code
        };
        queryChooseCourse(queryParam).done(function(resp) {
            var code = resp.code;
            if (code != null && code == '1') {
                buildCourseResultList(resp.dataList);
            } else if (code != null && code == '302') {
                sessionStorage.removeItem('token');
                sessionStorage.removeItem('studentInfo');
                window.location.href = BaseUrl + '/sys/xsxkapp/*default/index.do';
            } else {
                queryError();
            }
        });
    }

    function buildCourseResultList(dataList) {
        if (dataList != null && dataList.length > 0) {
            var html = '';
            var length = dataList.length;
            var kcList = [];
            var testList = [];
            var a = 0, b = 0;
            
            for (a = 0; a < length; a++) {
                if (dataList[a].isTest == '1') {
                	testList.push(dataList[a]);
                }else{
                	kcList.push(dataList[a]);
                }
            }
            var kcLength = kcList.length;
            var testLength = testList.length;
            
            var jcdgShow = 'cv-hide';
            var bookParam = JSON.parse(sessionStorage.getItem('bookParam'));
            if(bookParam.needBook == '1'){
            	jcdgShow = 'cv-show';
            }
            for (a = 0; a < kcLength; a++) {
            	var data = kcList[a];
            	var rowTemplate = $('#tpl-selectcourse-list-row').html();
                	
            	//rowTemplate = $('#tpl-selectcourse-test-list-row').html();
                
            	var courseTypeName = data.courseTypeName;
                if (courseTypeName == null) {
                    courseTypeName = '-';
                }

                var courseNatureName = data.courseNatureName;
                if (courseNatureName == null) {
                	courseNatureName = '-';
                }

                var teacherName = data.teacherName;
                if (teacherName == null) {
                    teacherName = '未安排教师';
                }

                var teachingPlace = data.teachingPlace;
                if (teachingPlace == null) {
                    teachingPlace = '未安排时间地点';
                }

                var isConflict = data.isConflict;
                if (isConflict != null && isConflict == '1') {
                    isConflict = '冲突';
                } else {
                    isConflict = '不冲突';
                }
                var conflictDesc = data.conflictDesc;
                if (conflictDesc == null) {
                    conflictDesc = "";
                }

                var courseName = data.courseName;
                var sportName = data.sportName;
                if (courseName == null) {
                    courseName = '-';
                }
                if (sportName != null) {
                    courseName = courseName + '(' + sportName + ')';
                }

                var campusName = data.campusName;
                if (campusName == null) {
                    campusName = '-';
                }

                var publicCourseTypeName = data.publicCourseTypeName;
                if (publicCourseTypeName == null) {
                	publicCourseTypeName = '-';
                }

                var isDisabled = '';
                var electiveIsOpen = sessionStorage.getItem('electiveIsOpen');
                var isTest = data.isTest;
                if ((electiveIsOpen != null && electiveIsOpen == '1') && (isTest == null || isTest != '1')) {
                    isDisabled = '';
                } else {
                    isDisabled = 'disabled="disabled"';
                }
                
                var isDisabledJf = '';
                var isNeedPay = data.isNeedPay?data.isNeedPay:'0';
                if (isNeedPay && isNeedPay == '1') {
                	isDisabledJf = '';
                } else {
                	isDisabledJf = 'disabled="disabled"';
                }

                var isTest = data.isTest;
                if (isTest != null && isTest == '1') {
                    courseTypeTip = '实验课';
                } else {
                    courseTypeTip = '理论课';
                }

                var bookBtnHtml = '';
                var bookParam = JSON.parse(sessionStorage.getItem('bookParam'));
            	if(bookParam.canSelectBook == '1' && data.needBook != '1'){
            		bookBtnHtml += '<a href="javascript:void(0)" teachingClassID="' + data.teachingClassID + '" class="course-book">订购教材</a>';
            	}
            	if(bookParam.canDeleteBook == '1' && data.needBook == '1'){
            		bookBtnHtml += '<a href="javascript:void(0)" teachingClassID="' + data.teachingClassID + '" class="course-unbook">退订教材</a>';
            	}
            	var needbook = '';
                if(bookParam.needBook == '1'){
                	if(data.needBook == '1'){
                		needbook = '已订购';
                	}else{
                		needbook = '未订购';
                	}
                }
                var schoolTerm = data.schoolTerm?data.schoolTerm:'-';
                var courseNumberPay = data.courseNumber?data.courseNumber:'-';
                var code = data.studentCode?data.studentCode:'-';
                
                var courseNature = data.courseNature?data.courseNature:'';
                var courseType = data.courseType?data.courseType:'';
                var publicCourseType = data.publicCourseType?data.publicCourseType:'-';
                var courseIndex = data.courseIndex?data.courseIndex:'';
                
                var paymentStatus = data.paymentStatus?data.paymentStatus:'无需缴费';
                html += rowTemplate.replace('@courseNumber', data.courseNumber + '[' + data.courseIndex + ']')
                    .replace('@courseName', courseName)
                    .replace('@teacherName', teacherName)
                    .replace('@courseNaturePay', courseNature)
                    .replace('@courseTypePay', courseType)
                    .replace('@publicCourseTypePay', publicCourseType)
                    .replace('@courseIndexPay', courseIndex)
                    .replace('@courseNatureNamePay', courseNatureName)
                    .replace('@courseTypeNamePay', courseTypeName)
                    .replace('@publicCourseTypeNamePay', publicCourseTypeName)
                    .replace('@courseNamePay', courseName)
                    .replace('@courseNatureName', courseNatureName)
                    .replace('@courseTypeName', courseTypeName)
                    .replace('@publicCourseTypeName', publicCourseTypeName)
                    .replace('@teachingPlace', teachingPlace)
                    .replace('@credit', data.credit)
                    .replace('@hours', data.hours)
                    .replace('@campusName', campusName)
                    .replace(/@teachingClassID/g, data.teachingClassID)
                    .replace('@isConflict', isConflict)
                    .replace('@conflictDesc', conflictDesc)
                    .replace('@bookBtnHtml', bookBtnHtml)
                    .replace('@jcdgShow', jcdgShow)
                    .replace('@needbook', needbook)
                    .replace('@isDisabled', isDisabled)
                    .replace('@paymentStatus', paymentStatus)
                    .replace('@code', code)
                    .replace('@schoolTerm', schoolTerm)
                    .replace('@courseNumberPay', courseNumberPay)
                    .replace('@isDisabledJf',isDisabledJf);
                
                if(data.hasTest == '1'){
                	for (b = 0; b < testLength; b++) {
                		var test_data = testList[b];
                		if(test_data.teachingClassID == data.testTeachingClassID){
                			var test_rowTemplate = $('#tpl-selectcourse-test-list-row').html();
                			
                			var test_courseTypeName = test_data.courseTypeName;
                			if (test_courseTypeName == null) {
                				test_courseTypeName = '-';
                			}
                			
                			var test_courseNatureName = test_data.courseNatureName;
                			if (test_courseNatureName == null) {
                				test_courseNatureName = '-';
                			}

                			var test_publicCourseTypeName = test_data.publicCourseTypeName;
                			if (test_publicCourseTypeName == null) {
                				test_publicCourseTypeName = '-';
                			}
                			
                			var test_teacherName = test_data.teacherName;
                			if (test_teacherName == null) {
                				test_teacherName = '未安排教师';
                			}
                			
                			var test_teachingPlace = test_data.teachingPlace;
                			if (test_teachingPlace == null) {
                				test_teachingPlace = '未安排时间地点';
                			}
                			
                			var test_isConflict = test_data.isConflict;
                			if (test_isConflict != null && test_isConflict == '1') {
                				test_isConflict = '冲突';
                			} else {
                				test_isConflict = '不冲突';
                			}
                			var test_conflictDesc = test_data.conflictDesc;
                			if (test_conflictDesc == null) {
                				test_conflictDesc = "";
                			}
                			
                			var test_courseName = test_data.courseName;
                			var test_sportName = test_data.sportName;
                			if (test_courseName == null) {
                				test_courseName = '-';
                			}
                			if (test_sportName != null) {
                				test_courseName = test_courseName + '(' + test_sportName + ')';
                			}
                			
                			var test_campusName = test_data.campusName;
                			if (test_campusName == null) {
                				test_campusName = '-';
                			}
                			
                			var test_isDisabled = '';
                			var test_electiveIsOpen = sessionStorage.getItem('electiveIsOpen');
                			var test_isTest = test_data.isTest;
                			if ((test_electiveIsOpen != null && test_electiveIsOpen == '1') && (test_isTest == null || test_isTest != '1')) {
                				test_isDisabled = '';
                			} else {
                				test_isDisabled = 'disabled="disabled"';
                			}
                			
                			var test_isTest = test_data.isTest;
                			if (test_isTest != null && test_isTest == '1') {
                				test_courseTypeTip = '实验课';
                			} else {
                				test_courseTypeTip = '理论课';
                			}
                			var test_needbook = '';
                            if(bookParam.needBook == '1'){
                            	if(test_data.needBook == '1'){
                            		test_needbook = '已订购';
                            	}else{
                            		test_needbook = '未订购';
                            	}
                            }
                			html += test_rowTemplate.replace('@courseNumber', test_data.courseNumber + '[' + test_data.courseIndex + ']')
                			.replace('@courseName', test_courseName)
                			.replace('@teacherName', test_teacherName)
                			.replace('@courseNatureName', test_courseNatureName)
                			.replace('@courseTypeName', test_courseTypeName)
                			.replace('@publicCourseTypeName', test_publicCourseTypeName)
                			.replace('@teachingPlace', test_teachingPlace)
                			.replace('@credit', test_data.credit)
                			.replace('@hours', test_data.hours)
                			.replace('@campusName', test_campusName)
                			.replace('@teachingClassID', test_data.teachingClassID)
                			.replace('@isConflict', test_isConflict)
                			.replace('@conflictDesc', test_conflictDesc)
                			.replace('@jcdgShow', jcdgShow)
                			.replace('@needbook', test_needbook)
                			.replace('@isDisabled', test_isDisabled);
                		}
                    }
                }
            }
            $('#selectedCourse').html(html);

            var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
            var electiveBatch = studentInfo.electiveBatch;
            var electiveTacticCode = electiveBatch.tacticCode;
            if (electiveTacticCode != null && electiveTacticCode == '02') {
                $('.withdrew').attr('disabled', 'disabled');
                $('.pay').attr('disabled', 'disabled');
            } else {
                // 绑定删除事件
                $('.withdrew').on('click', function(event) {
                    var disabled = $(event.currentTarget).attr('disabled');
                    if (disabled == null) {
                   	var electiveIsOpen = sessionStorage.getItem('electiveIsOpen');
                       var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
                       var electiveBatch = studentInfo.electiveBatch;
                       //若未开放，则重新请求是否开放
                       if(!electiveIsOpen || electiveIsOpen != '1'){
                       	var resp = queryXklcSfkfBySync({xklcdm: electiveBatch.code});
                   		if(resp.msg == '1'){
                   			sessionStorage.setItem('electiveIsOpen', '1');
                   			electiveIsOpen = '1';
                   		}
                       }
                       //判断是否开放
                       if (!electiveIsOpen || electiveIsOpen != '1') {
                       	$.bhTip({
                   			content: '轮次未开放',
                   			state: 'danger'
                   		});
                       	return false;
                       }
                       CVDeleteCourseResults.deleteResult(event);
                   }
               });
                // 绑定缴费事件
                $('.pay').on('click', function(event) {
                    var disabled = $(event.currentTarget).attr('disabled');
                    if (disabled == null) {
                   	var electiveIsOpen = sessionStorage.getItem('electiveIsOpen');
                       var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
                       var electiveBatch = studentInfo.electiveBatch;
                       //若未开放，则重新请求是否开放
                       if(!electiveIsOpen || electiveIsOpen != '1'){
                       	var resp = queryXklcSfkfBySync({xklcdm: electiveBatch.code});
                   		if(resp.msg == '1'){
                   			sessionStorage.setItem('electiveIsOpen', '1');
                   			electiveIsOpen = '1';
                   		}
                       }
                       //判断是否开放
                       if (!electiveIsOpen || electiveIsOpen != '1') {
                       	$.bhTip({
                   			content: '轮次未开放',
                   			state: 'danger'
                   		});
                       	return false;
                       }
                       CVPayCourseResults.payResult(event);
                   }
               });
            }
            $('#cvSelectCourse .cv-selected-course').off('click', '.course-book').on('click', '.course-book', function(e){
            	var dialogData = new Object();
                dialogData.title = '确认订购教材';
                dialogData.content = '确认订购这门课程的教材吗？';
                dialogData.type = 'course-book';
                CVDialogSelectCourse.show(dialogData, e);
            });
            $('#cvSelectCourse .cv-selected-course').off('click', '.course-unbook').on('click', '.course-unbook', function(e){
            	var dialogData = new Object();
            	dialogData.title = '确认退订教材';
            	dialogData.content = '确认退订这门课程的教材吗？';
            	dialogData.type = 'course-unbook';
            	CVDialogSelectCourse.show(dialogData, e);
            });
            $('#cvSelectCourse .cv-selected-course').off('click', '.cv-jcDetail').on('click', '.cv-jcDetail', function(e){
            	var jxbid = $(e.currentTarget).attr('tcid');
            	window.open(BaseUrl + '/sys/xsxkapp/*default/jcdetail.do?jxbid=' + jxbid);
            });
        } else {
            $('#selectedCourse').html('没有已选课程');
        }
        
    }

    function queryError() {
        $('#cvSelectCourse').html('<p>数据异常，请稍后重试。</p>');
    }

})(window.CVCourseResult = window.CVCourseResult || {});

/**
 * 删除选课结果
 */
;
(function(_public) {

    _public.deleteResult = function(e) {
        deleteCourseResult(e);
    };

    function deleteCourseResult(e) {
        var electiveIsOpen = sessionStorage.getItem('electiveIsOpen');
        if (electiveIsOpen != null && electiveIsOpen == '1') {
            var dialogData = new Object();
            dialogData.title = '确认退选';
            dialogData.content = '确认退选这门课程吗？';
            dialogData.type = 'withdrew';
            CVDialogSelectCourse.show(dialogData, e);
        }
    }
})(window.CVDeleteCourseResults = window.CVDeleteCourseResults || {});

/**
 * 缴费选课结果
 */
;
(function(_public) {

    _public.payResult = function(e) {
        payCourseResult(e);
    };

    function payCourseResult(e) {
        var electiveIsOpen = sessionStorage.getItem('electiveIsOpen');
        if (electiveIsOpen != null && electiveIsOpen == '1') {
            var dialogData = new Object();
            dialogData.title = '确认缴费';
            dialogData.content = '确认缴费这门课程吗？';
            dialogData.type = 'pay';
            CVDialogSelectCourse.show(dialogData, e);
        }
    }
})(window.CVPayCourseResults = window.CVPayCourseResults || {});

/**
 * 对话框
 */
;
(function(_dialog) {
    /**
     * 显示对话框
     * @param _data {object}
     * @param _data.title {string} 课程标题
     */
    _dialog.show = function(_data, e) {
        showDialog(_data, e);
    };

    _dialog.showSuccess = function(_data) {
        showSuccess(_data);
    };

    _dialog.showDanger = function(_data) {
        showDanger(_data);
    };

    /**
     * 移除弹框
     */
    _dialog.remove = function() {
        removeDialog();
    };

    function showSuccess(_data) {
        var template =
            '<div id="cvDialog" class="cv-dialog cv-success">' +
            '<div>' +
            '<div class="cv-body">' +
            '<img class="cv-mb-16" src="public/images/curriculaVariable/dialog-icon.png">' +
            '<h2 class="cv-mb-8">@title</h2>' +
            '<div>@content</div>' +
            '</div>' +
            '<div class="cv-foot">' +
            '<div class="cv-sure cvBtnFlag">确认</div>' +
            '</div>' +
            '</div>' +
            '</div>';
        var title = _data.title;
        var content = _data.content;
        var html = template.replace('@title', title).replace('@content', content);

        var $dialog = $(html);
        $('body').append($dialog);

        //点击页脚按钮的事件
        $dialog.on('click', '.cvBtnFlag', function() {
            btnHandle($(this));
        });
    }

    function showDanger(_data) {
        var template =
            '<div id="cvDialog" class="cv-dialog cv-danger">' +
            '<div>' +
            '<div class="cv-body">' +
            '<img class="cv-mb-16" src="public/images/curriculaVariable/dialog-icon.png">' +
            '<h2 class="cv-mb-8">@title</h2>' +
            '<div>@content</div>' +
            '</div>' +
            '<div class="cv-foot">' +
            '<div class="cv-sure cvBtnFlag">确认</div>' +
            '</div>' +
            '</div>' +
            '</div>';
        var title = _data.title;
        var content = _data.content;
        var html = template.replace('@title', title).replace('@content', content);

        var $dialog = $(html);
        $('body').append($dialog);

        //点击页脚按钮的事件
        $dialog.on('click', '.cvBtnFlag', function() {
            btnHandle($(this));
        });
    }

    /**
     * 显示对话框
     * @param _data {object}
     * @param _data.title {string} 课程标题
     */
    function showDialog(_data, e) {
        var template =
            '<div id="cvDialog" class="cv-dialog @type">' +
            '<div>' +
            '<div class="cv-body">' +
            '<img class="cv-mb-16" src="public/images/curriculaVariable/dialog-icon.png">' +
            '<h2 class="cv-mb-8">@title</h2>' +
            '<div>@content</div>' +
            '</div>' +
            '<div class="cv-foot">' +
            '<div class="cv-sure cvBtnFlag" type="sure">确认</div>' +
            '<div class="cv-cancel cvBtnFlag" type="cancel">取消</div>' +
            '</div>' +
            '</div>' +
            '</div>';

        var title = _data.title;
        var content = _data.content;
        var html = template.replace('@title', title).replace('@content', content);

        var $dialog = $(html);
        $('body').append($dialog);

        //点击页脚按钮的事件
        $dialog.on('click', '.cvBtnFlag', function() {
            btnHandle($(this), e, _data.type);
        });
    }

    /**
     * 点击页脚按钮的事件
     * @param $btn 被点击的按钮
     */
    function btnHandle($btn, e, btnType) {
        var type = $btn.attr('type');
        //退选
        if (type === 'sure') {
            sureHandle(e, btnType);
        } else {
            //取消
            cancelHandle();
        }
    }

    /**
     * 取消
     */
    function cancelHandle() {
        removeDialog();
    }

    /**
     * 确认退选
     */
    function sureHandle(e, btnType) {
    	removeDialog();
    	if(btnType == 'course-book'){
    		bookJxbJc(e);
    	}else if(btnType == 'course-unbook'){
    		unbookJxbJc(e);
    	}else if(btnType == 'pay'){
    		pay(e);
    	}else if(btnType == 'surePay'){
    		$('#cvDialog').remove();
    		CVCourseResult.init();
    	}else {
    		deleteVolunteer(e);
    	}
    }

    /**
     * 移除弹框
     */
    function removeDialog() {
        $('#cvDialog').remove();
    }
    
    function bookJxbJc(e){
    	var teachingClassID = $(e.currentTarget).attr('teachingClassID');
    	var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
        var studentCode = studentInfo.code; // 学号
        var electiveBatch = studentInfo.electiveBatch;
        var electiveBatchCode = electiveBatch.code;
        var addParam = {
    		xklcdm: electiveBatchCode,
    		xh: studentCode,
    		jxbid: teachingClassID
        };
        bookJxbJcResult(addParam).done(function(resp) {
            var code = resp.code;
            if (code != null && code == '1') {
                $('#cvDialog').remove();
                CVCourseResult.init();
                $.bhTip({
                    content: '订购教材成功',
                    state: 'success'
                });
            } else {
                var failObj = new Object();
                failObj.title = '失败';
                failObj.content = resp.msg;
                CVDialogSelectCourse.remove();
                CVDialogSelectCourse.showDanger(failObj);
            }
        });
    }
    
    function unbookJxbJc(e){
    	var teachingClassID = $(e.currentTarget).attr('teachingClassID');
    	var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
    	var studentCode = studentInfo.code; // 学号
    	var electiveBatch = studentInfo.electiveBatch;
    	var electiveBatchCode = electiveBatch.code;
    	var addParam = {
    			xklcdm: electiveBatchCode,
    			xh: studentCode,
    			jxbid: teachingClassID
    	};
    	delBookJxbJcResult(addParam).done(function(resp) {
    		var code = resp.code;
    		if (code != null && code == '1') {
    			$('#cvDialog').remove();
    			CVCourseResult.init();
    			$.bhTip({
    				content: '退订教材成功',
    				state: 'success'
    			});
    		} else {
    			var failObj = new Object();
    			failObj.title = '失败';
    			failObj.content = resp.msg;
    			CVDialogSelectCourse.remove();
    			CVDialogSelectCourse.showDanger(failObj);
    		}
    	});
    }
    
    //缴费
    function pay(e) {
        var schoolTerm = $(e.currentTarget).attr('schoolTerm');
        var courseNumber = $(e.currentTarget).attr('courseNumberPay');
        var courseName = $(e.currentTarget).attr('courseNamePay');
        var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
        //校公选课类别
        var publicCourseTypeName = $(e.currentTarget).attr('publicCourseTypeName');
        var publicCourseType = $(e.currentTarget).attr('publicCourseType');
        //课序号
        var courseIndex = $(e.currentTarget).attr('courseIndex');
        //课程性质
        var courseNatureName = $(e.currentTarget).attr('courseNatureName');
        var courseNature = $(e.currentTarget).attr('courseNature');
        //课程类别
        var courseTypeName = $(e.currentTarget).attr('courseTypeName');
        var courseType = $(e.currentTarget).attr('courseType');
        var studentCode = studentInfo.code; // 学号
        var electiveBatch = studentInfo.electiveBatch;
        var electiveBatchCode = electiveBatch.code;
        var payData = '{"courseName":"' + courseName + '"' + ',"courseType":"' + courseType + '"' + ',"courseTypeName":"' + courseTypeName + '"' + ',"courseNature":"' + courseNature + '"' + ',"courseNatureName":"' + courseNatureName + '"' + ',"courseIndex":"' + courseIndex + '"' + ',"publicCourseType":"' + publicCourseType + '"' + ',"publicCourseTypeName":"' + publicCourseTypeName + '"' + ',"courseNumber":"' + courseNumber + '"' + ',"schoolTerm":"'+schoolTerm+'"' + ',"studentCode":"' + studentCode + '"' + ',"electiveBatchCode":"' + electiveBatchCode + '"' + '}';
        var payStr = '{"data":' + payData + '}';
        var payParam = {
            'payParam': payStr
        };
        payResult(payParam).done(function(resp) {
            var code = resp.code;
            var msg =  resp.msg;
            if (code != null && code == '1') {
            	if(msg){
            		$('#cvDialog').remove();
                	window.open(msg, "_blank");
                	 var dialogData = new Object();
                     dialogData.title = '确认';
                     dialogData.content = '是否完成支付？';
                     dialogData.type = 'surePay';
                     CVDialogSelectCourse.show(dialogData, e);
            	}else{
            		var failObj = new Object();
                    failObj.title = '失败';
                    failObj.content = '发起缴费失败,请刷新页面后再试';
                    CVDialogSelectCourse.remove();
                    CVDialogSelectCourse.showDanger(failObj);
            	}
            } else if (code == '302') {
                sessionStorage.removeItem('token');
                sessionStorage.removeItem('studentInfo');
                window.location.href = BaseUrl + '/sys/xsxkapp/*default/index.do';
            } else {
                var failObj = new Object();
                failObj.title = '失败';
                failObj.content = resp.msg;
                CVDialogSelectCourse.remove();
                CVDialogSelectCourse.showDanger(failObj);
            }
        });
    }
    
    function deleteVolunteer(e) {
        var teachingClassID = $(e.currentTarget).attr('teachingClassID');
        var studentInfo = JSON.parse(sessionStorage.getItem('studentInfo'));
        var studentCode = studentInfo.code; // 学号
        var electiveBatch = studentInfo.electiveBatch;
        var electiveBatchCode = electiveBatch.code;
        var delData = '{"operationType":"2"' + ',"studentCode":"' + studentCode + '"' + ',"electiveBatchCode":"' + electiveBatchCode + '"' + ',"teachingClassId":"' + teachingClassID + '"' + ',"isMajor":"1"}';
        var delStr = '{"data":' + delData + '}';
        var deleteParam = {
            'deleteParam': delStr
        };
        deleteVolunteerResult(deleteParam).done(function(resp) {
            var code = resp.code;
            if (code != null && code == '1') {
            	$('#cvDialog').remove();
                initProcessInterval(function(processResp){
                	CVCourseResult.init();
                	if(processResp.code == '1'){
                		$.bhTip({
                			content: '删除选课成功',
                			state: 'success'
                		});
                	}else if(processResp.code == '-1'){
                		$.bhTip({
                			content: processResp.msg,
                			state: 'danger'
                		});
                	}
                	// 查询已选课程数量
                	querySelectCourseNum();
                });
            } else if (code == '302') {
                sessionStorage.removeItem('token');
                sessionStorage.removeItem('studentInfo');
                window.location.href = BaseUrl + '/sys/xsxkapp/*default/index.do';
            } else {
                var failObj = new Object();
                failObj.title = '失败';
                failObj.content = resp.msg;
                CVDialogSelectCourse.remove();
                CVDialogSelectCourse.showDanger(failObj);
            }
        });
    }
})(window.CVDialogSelectCourse = window.CVDialogSelectCourse || {});

function initSelectCourse() {
	var bookParam = JSON.parse(sessionStorage.getItem('bookParam'));
    if(bookParam.needBook != '1'){
    	$('#cvSelectCourse .cv-jcBook').hide();
    }
    
    var sysParam = JSON.parse(sessionStorage.getItem('sysParam'));
    if(sysParam.xgxkQueryTitle){
    	changeTskName(sysParam.xgxkQueryTitle);
    }
    if(sysParam.kclbNotDisplay == '1'){
    	$('#cvSelectCourse').addClass('no-kclb');
    }
    // 初始化学生选课结果
    CVCourseResult.init();
}