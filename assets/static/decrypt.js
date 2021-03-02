/**
 * @classdesc Decrypt content encrypted with AES-GCM
 */
class Decryptor {
    /**
     * Create an object that can decrypt content using the specified key
     *
     * @constructor
     * @param {string} base64key - 128-bit, base64-encoded encryption key
     * @return {Promise<Decryptor>}
     */
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
    /**
     * @param {Uint8Array} data
     * @return {Promise<ArrayBuffer>}
     */
    async decrypt(data) {
        return await crypto.subtle.decrypt(
            {'name': 'AES-GCM', 'iv': data.subarray(0, 12)},
            this.key, data.subarray(12));
    }
    /**
     * Decrypt encrypted text to a string
     *
     * @param {Uint8Array} data
     * @return {Promise<string>}
     */
    async toText(data) {
        let decoder = new TextDecoder();
        return decoder.decode(await this.decrypt(data));
    }
    /**
     * Decrypt encrypted binary data to an object URL
     *
     * @param {Uint8Array} data
     * @param {string} type - the decrypted object's MIME type
     * @return {Promise<DOMString>} Promise that resolves to an object URL DOMString
     */
    async toObjectURL(data, type) {
        const decrypted = await this.decrypt(data);
        const blob = new Blob([decrypted], {"type": type});
        return URL.createObjectURL(blob);
    }
}

/**
 * @typedef {Object} EncryptedData
 * @property {Uint8Array} data
 * @property {string} type - MIME type
 */

/**
 * Fetch data from a URL and return it and its MIME type
 *
 * @param {string|URL} url - data to fetch, accepts any type the Fetch API supports
 * @return {EncryptedData}
 */
async function fetchData(url) {
    const response = await fetch(url);
    const buffer = await response.arrayBuffer();
    return {
        'data': new Uint8Array(buffer),
        'type': response.headers.get('Content-Type')
    };
}
/**
 * Fetch data at the specified URL and decrypt it to an object URL
 *
 * @param {string|URL} url
 * @param {Decryptor} decryptor
 * @param {string} [type=image/jpeg] - MIME type to use for the returned object URL
 * @return {Promise<DOMString>} Promise that resolves to an object URL DOMString
 */
async function fetchDecryptedObject(url, decryptor, type = 'image/jpeg') {
    const source = await fetchData(url);
    return await decryptor.toObjectURL(source.data, type);
}
/**
 * Decrypt requested image and load it into the DOM where it is used
 *
 * @param {string|URL} url
 * @param {Decryptor} decryptor
 * @param {string} [type=image/jpeg]
 * @return {undefined}
 */
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
/**
 * Add images to IntersectionObserver to be decrypted and displayed later
 *
 * @param {Decryptor} decryptor
 * @param {NodeList} elements
 * @return {undefined}
 */
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
/**
 * Add panorama images to IntersectionObserver to be decrypted and displayed later
 *
 * @param {Decryptor} decryptor
 * @param {NodeList} elements
 */
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
/**
 * Fetch and decrypt content and load it into an HTML element
 *
 * @param {string} base64key
 * @param {string|URL} url
 * @return {Element}
 */
async function decryptContent(base64key, url) {
    let decryptor = await new Decryptor(base64key);
    const content = await decryptor.toText((await fetchData(url)).data);
    let container = document.createElement('article');
    container.innerHTML = content;
    decryptImages(decryptor, container.querySelectorAll('.media img'));
    decryptPanoramas(decryptor, container.querySelectorAll('.media .panorama'));
    return container;
}

export { Decryptor, decryptContent, fetchDecryptedObject };
