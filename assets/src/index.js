function isValidKey(key) {
    try {
        return atob(key).length == 16;
    } catch (e) {
        return false;
    }
}

let anchor = location.hash.substr(1);
if (anchor && isValidKey(anchor)) {
    sessionStorage.setItem('key', anchor);
    history.replaceState({}, '', location.href.replace(location.hash, ''));
}

import { decryptContent } from "./decrypt.js";

addEventListener('DOMContentLoaded', () => {
    decryptContent(sessionStorage.getItem('key'), 'content')
        .then(value => {
            document.body.classList.add('unlocked');
            document.body.appendChild(value);
        })
        .catch(() => {});
});
