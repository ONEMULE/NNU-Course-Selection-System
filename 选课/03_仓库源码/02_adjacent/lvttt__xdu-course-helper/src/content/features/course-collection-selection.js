export function isCollectedCourse(collectionData, bjdm) {
    return Array.isArray(collectionData)
        ? collectionData.some((item) => item?.BJDM === bjdm)
        : false;
}

export function resolveBulkCollectionSelection(checkboxIds, collectionData, checked) {
    const checkedStateById = {};
    const selectedCourseIds = [];

    (Array.isArray(checkboxIds) ? checkboxIds : []).forEach((bjdm) => {
        const canSelect = checked && isCollectedCourse(collectionData, bjdm);
        checkedStateById[bjdm] = canSelect;
        if (canSelect) {
            selectedCourseIds.push(bjdm);
        }
    });

    return {
        checkedStateById,
        selectedCourseIds,
    };
}
