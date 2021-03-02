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
function decryptImage(url, decryptor, type = 'image/jpeg') {
    fetchDecryptedObject(url, decryptor, type).then(object => {
        // Update all the images using the same URL:
        for (let image of document.querySelectorAll(`img[data-src="${url}"]`)) {
            delete image.dataset.src;
            // Revoking multiple times doesn't seem to hurt:
            image.addEventListener('load', (e) => URL.revokeObjectURL(e.target.src));
            image.src = object;
        }
    });
}
function decryptImages(decryptor, elements) {
    if (elements) {
        let observer = new IntersectionObserver(entries => {
            for (let entry of entries) {
                let image = entry.target;
                if (entry.isIntersecting && 'src' in image.dataset) {
                    decryptImage(image.dataset.src, decryptor);
                }
            }
        }, {rootMargin: '50px'});
        for (let image of elements) {
            observer.observe(image);
        }
    }
}
function decryptPanoramas(decryptor, elements) {
    if (elements) {
        import("./panorama.js").then(module => {
            let observer = new IntersectionObserver(module.getPanoramaCallback(decryptor));
            for (let panorama of elements) {
                observer.observe(panorama);
            }
        });
    }
}
async function decryptContent(base64key, url) {
    let decryptor = await new Decryptor(base64key);
    const content = await decryptor.toText((await fetchEncryptedData(url)).data);
    let container = document.createElement('article');
    container.innerHTML = content;
    decryptImages(decryptor, container.querySelectorAll('.media img'));
    decryptPanoramas(decryptor, container.querySelectorAll('.media .panorama'));
    return container;
}

export { Decryptor, decryptContent, fetchDecryptedObject };
