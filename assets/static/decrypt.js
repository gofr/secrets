"use strict";
(function() {

function toByteArray(base64string) {
    // https://stackoverflow.com/a/41106346/23263
    return Uint8Array.from(atob(base64string), c => c.charCodeAt(0));
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
    return URL.createObjectURL(blob);
}
async function fetchEncryptedData(url) {
    const response = await fetch(url);
    const buffer = await response.arrayBuffer();
    return {
        'data': new Uint8Array(buffer),
        'type': response.headers.get('Content-Type')
    };
}
async function fetchDecryptedObject(url, base64key, type = 'image/jpeg') {
    const source = await fetchEncryptedData(url);
    return await decryptToObjectURL(base64key, source.data, type);
}
async function decryptImage(base64key, url, type = 'image/jpeg') {
    let object = await fetchDecryptedObject(url, base64key, type);
    // Update all the images using the same URL:
    for (let image of document.querySelectorAll(`img[data-src="${url}"]`)) {
        delete image.dataset.src;
        // Revoking multiple times doesn't seem to hurt:
        image.addEventListener('load', (e) => URL.revokeObjectURL(e.target.src));
        image.src = object;
    }
}
function decryptImages(base64key) {
    return async function imageDecryptCallback(entries, observer) {
        for (let entry of entries) {
            let image = entry.target;
            if (entry.isIntersecting && 'src' in image.dataset) {
                await decryptImage(base64key, image.dataset.src);
            }
        }
    }
}
async function decryptContent(base64key, url) {
    const content = await decryptToText(base64key, (await fetchEncryptedData(url)).data);
    let container = document.createElement('article');
    container.innerHTML = content;
    var observer = new IntersectionObserver(decryptImages(base64key), {rootMargin: '50px'});
    for (let image of container.querySelectorAll('.media img')) {
        observer.observe(image);
    }
    if (panoramaObserver) {
        for (let panorama of container.querySelectorAll('.media .panorama')) {
            panoramaObserver.observe(panorama);
        }
    }
    return container;
}

window.decryptContent = decryptContent;
window.fetchDecryptedObject = fetchDecryptedObject;

})();
