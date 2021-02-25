"use strict";

class Decryptor {
    constructor(base64key) {
        // https://stackoverflow.com/a/41106346
        const byteKey = Uint8Array.from(atob(base64key), c => c.charCodeAt(0));
        // This is a bit awkward: https://stackoverflow.com/a/50885340
        return (async () => {
            this.key = await crypto.subtle.importKey(
                "raw", byteKey, "AES-GCM", false, ["decrypt"]);
            return this;
        })();
    }

    async decrypt(data) {
        return await crypto.subtle.decrypt(
            {'name': 'AES-GCM', 'iv': data.subarray(0, 12)},
            this.key, data.subarray(12));
    }

    async toText(data) {
        let decoder = new TextDecoder();
        return decoder.decode(await this.decrypt(data));
    }

    async toObjectURL(data, type) {
        const decrypted = await this.decrypt(data);
        const blob = new Blob([decrypted], {"type": type});
        return URL.createObjectURL(blob);
    }
}

(function() {

async function fetchEncryptedData(url) {
    const response = await fetch(url);
    const buffer = await response.arrayBuffer();
    return {
        'data': new Uint8Array(buffer),
        'type': response.headers.get('Content-Type')
    };
}
async function fetchDecryptedObject(url, decryptor, type = 'image/jpeg') {
    const source = await fetchEncryptedData(url);
    return await decryptor.toObjectURL(source.data, type);
}
async function decryptImage(decryptor, url, type = 'image/jpeg') {
    let object = await fetchDecryptedObject(url, decryptor, type);
    // Update all the images using the same URL:
    for (let image of document.querySelectorAll(`img[data-src="${url}"]`)) {
        delete image.dataset.src;
        // Revoking multiple times doesn't seem to hurt:
        image.addEventListener('load', (e) => URL.revokeObjectURL(e.target.src));
        image.src = object;
    }
}
function decryptImages(decryptor) {
    return async function imageDecryptCallback(entries, observer) {
        for (let entry of entries) {
            let image = entry.target;
            if (entry.isIntersecting && 'src' in image.dataset) {
                await decryptImage(decryptor, image.dataset.src);
            }
        }
    }
}
async function decryptContent(base64key, url) {
    let decryptor = await new Decryptor(base64key);
    const content = await decryptor.toText((await fetchEncryptedData(url)).data);
    let container = document.createElement('article');
    container.innerHTML = content;
    var observer = new IntersectionObserver(decryptImages(decryptor), {rootMargin: '50px'});
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
