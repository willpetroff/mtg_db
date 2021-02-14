var iconSelected = '';

var toggleIcon = function(button_object, disable){
    var $item = button_object;
    var $icon;
    if (!$item) {
        return false;
    }
    if ($item.is('button') || $item.is('span')){
        $icon = $($item.children('i'));
    } else {
        $icon = $item;
    }
    var iconClassList = $icon.attr('class').split(' ');
    var iconTarget;
    if (!iconSelected){
        iconClassList.forEach(function(classStr){
            //console.log(classStr)
            if (classStr.indexOf('fa-') > -1 && classStr.indexOf('2x') == -1){
                iconTarget = classStr;
            }
        });
        iconSelected = iconTarget;
    } else {
        iconTarget = iconSelected;
        iconSelected = '';
    }
    if (disable){
        $item.prop('disabled', true);
    } else {
        $item.prop('disabled', false);
    }
    $icon.toggleClass(iconTarget);
    $icon.toggleClass('fa-sync-alt fa-spin');
};

var submitFormGeneral = function(activeObj, formData, submitPath) {
    toggleIcon(activeObj, true);
    $.ajax({
        type: 'POST',
        contentType: false,
        processData: false,
        async:true,
        url: submitPath,
        data: formData,
        success: function(data){
            if (data.success){
                if (data.msg) {
                    alert(data.msg);
                }
                if (data.redirect){
                    window.location.href = data.redirect;
                } else if (data.reload){
                    window.location.reload();
                }
                toggleIcon(activeObj, false);
            } else {
                alert(data.err);
                toggleIcon(activeObj, false);
                if (data.reload) {
                    window.location.reload();
                }
            }
            return true
        },
        error: function(){
            toggleIcon(activeObj, false);
            console.log('test', submitPath);
            alert('An error has occurred trying to communicate with the server; please try again. If the error persists, please contact the webmaster.');
        }
    });
}

var collectInputVals = function(inputTypes, formData) {
    if (Array.isArray(inputTypes)) {
        inputTypes.forEach(function(item){
            var itemDict = {};
            var categoryName = item.replace('-input', '');
            $('.' + item).each(function(){
                itemDict[$(this).attr('name')] = $(this).val();
            });
            formData.append(categoryName, JSON.stringify(itemDict));
        });
    } else {
        $('.' + inputTypes).each(function(){
            if ($(this).attr('type') == 'file') {
                for (var fileItem in $(this).prop('files')){
                    var addOn = '';
                    if (!$(this).attr('name')) {
                        addOn = fileItem;
                    }
                    formData.append($(this).attr('name') + addOn, $(this).prop('files')[fileItem]);
                }
            } else if ($(this).attr('type') == 'checkbox') {
                if ($(this).is(':checked')) {
                    formData.append($(this).attr('name'), 'true');
                } else {
                    formData.append($(this).attr('name'), 'false');
                }
            } else {
                formData.append($(this).attr('name'), $(this).val());
            }
        });   
    }
}