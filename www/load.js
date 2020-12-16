"use strict";
(function() {

function isValidKey(key) {
    try {
        return atob(key).length == 16;
    } catch (e) {
        return false;
    }
}

function getLastPathComponent(path) {
    let components = path.split('/');
    components.reverse();
    return components.find(item => item);
}

let anchor = location.hash.substr(1);
if (anchor && isValidKey(anchor)) {
    sessionStorage.setItem('key', anchor);
    history.replaceState({}, '', location.href.replace(location.hash, ''));
}
sessionStorage.setItem('dir', getLastPathComponent(location.pathname));

let ogTitle = document.head.querySelector('meta[property="og:title"]');
if (ogTitle) {
    let title = ogTitle.getAttribute('content');
    if (title) {
        let titleElement = document.createElement('title');
        titleElement.textContent = title;
        document.head.appendChild(titleElement);
    }
}
addEventListener('DOMContentLoaded', () => {
    decryptContent(sessionStorage.getItem('key'), 'content')
        .then(value => {
            document.body.appendChild(value);
        })
        .catch(reason => console.log(reason));
});

})();
