"use strict";
// TODO: Stop polluting the global namespace.

function toByteArray(base64string) {
    // https://stackoverflow.com/a/41106346/23263
    return Uint8Array.from(atob(base64string), c => c.charCodeAt(0))
}
async function decrypt(base64key, data) {
    const key = await crypto.subtle.importKey(
        'raw', toByteArray(base64key), 'AES-GCM', false, ['decrypt']);
    return await crypto.subtle.decrypt(
        {'name': 'AES-GCM', 'iv': data.subarray(0, 12)},
        key, data.subarray(12));
}
async function decryptToText(base64key, data) {
    let decoder = new TextDecoder();
    return decoder.decode(await decrypt(base64key, data));
}
async function decryptToObjectURL(base64key, data, type) {
    const decrypted = await decrypt(base64key, data);
    const blob = new Blob([decrypted], {"type": type});
    return URL.createObjectURL(blob)
}
async function fetchEncryptedData(url) {
    const response = await fetch(url);
    const buffer = await response.arrayBuffer();
    return {
        'data': new Uint8Array(buffer),
        'type': response.headers.get('Content-Type')
    }
}
async function decryptImages(base64key, selector) {
    let decrypted = {};
    for (let image of selector) {
        if ('src' in image.dataset) {
            let src = image.dataset.src;
            delete image.dataset.src;
            if (src in decrypted) {
                image.src = decrypted[src];
            } else {
                image.addEventListener('load', (e) => URL.revokeObjectURL(e.target.src));
                // TODO: Use an IntersectionObserver? Make sure to still avoid
                // multiple fetches for the same source. And do I need to make
                // sure an object URL isn't revoked before it is re-used?
                const source = await fetchEncryptedData(src);
                image.src = await decryptToObjectURL(base64key, source.data, 'image/jpeg');
                decrypted[src] = image.src;
            }
        }
    }
}
async function decryptContent(base64key, url) {
    const content = await decryptToText(base64key, (await fetchEncryptedData(url)).data);
    let container = document.createElement('article');
    container.innerHTML = content;
    decryptImages(base64key, container.querySelectorAll('img'));
    return container;
}
