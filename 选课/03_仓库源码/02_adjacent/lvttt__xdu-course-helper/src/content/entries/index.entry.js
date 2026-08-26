import { initCourseCollectionFeature } from '../features/course-collection';
import { claimGuard } from '../runtime/guard';

if (!claimGuard('content:index:bootstrap')) {
    console.warn('xdu-course-helper: content index already initialized');
} else {
    console.log('选课助手 Content Script 已加载');
    initCourseCollectionFeature();
}

