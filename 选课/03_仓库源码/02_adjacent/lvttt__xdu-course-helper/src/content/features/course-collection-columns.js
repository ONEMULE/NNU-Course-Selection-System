export function createCollectionGridColumns(sourceColumns, checkboxView = () => '') {
    const baseColumns = Array.isArray(sourceColumns)
        ? sourceColumns
              .filter((column) => column.display !== '操作' && column.display !== '课程类别')
              .map((column) => ({ ...column }))
        : [];

    const creditColumn = baseColumns.find((column) => column.display === '学分');
    if (creditColumn) {
        creditColumn.property = 'KCXF';
    }

    return [
        {
            display: '',
            width: '5%',
            align: 'center',
            view: checkboxView,
        },
        ...baseColumns,
    ];
}
