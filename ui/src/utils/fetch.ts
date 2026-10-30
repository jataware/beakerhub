import { URLExt } from '@jupyterlab/coreutils';

type DefaultHeaders = Record<string, HeadersInit>;

interface RequestInitWithBase extends RequestInit {
  baseUrl?: string;
  skipBase?: boolean;
};

class FetchClient {
  private defaultHeaders: DefaultHeaders;
  private baseUrl: string = '/';

  constructor(defaultHeaders: DefaultHeaders = {}) {
    this.defaultHeaders = defaultHeaders;
  }

  setDefaultHeaders(urlRegex: string|RegExp, headers: HeadersInit) {
    let key: string;
    if (urlRegex instanceof RegExp) {
      key = urlRegex.source;
    }
    else {
      key = urlRegex;
    }
    if (key in this.defaultHeaders) {
      this.defaultHeaders[key] = {...this.defaultHeaders[key], ...headers};
    }
    else {
      this.defaultHeaders[key] = headers;
    }
  }

  clearDefaultHeader(urlRegex: string|RegExp, headerName: string) {
    let key: string;
    if (urlRegex instanceof RegExp) {
      key = urlRegex.source;
    }
    else {
      key = urlRegex;
    }
    if (key in this.defaultHeaders && headerName in this.defaultHeaders[key]) {
      delete this.defaultHeaders[key][headerName];
    }

  }

  setBaseUrl(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private headersForUrl(url) {
    const absUrl = URLExt.parse(url).href;
    const defaultHeaders = this.defaultHeaders;
    const headers = Object.entries(defaultHeaders).reduce<HeadersInit>((prev, [regex, headers]) => {
      if (new RegExp(regex).test(absUrl)) {
        return {...prev, ...headers};
      }
      else {
        return prev;
      }
    }, {});
    return headers;
  }

  async fetch(url: string, options?: RequestInitWithBase): Promise<Response> {
    const {baseUrl, skipBase, ...requestOptions} = options || {};
    const headers = this.headersForUrl(url);
    const prefixedUrl = URLExt.parse(url);
    if (!skipBase) {
      const prefix = baseUrl || this.baseUrl;
      prefixedUrl.pathname = URLExt.join(prefix, prefixedUrl.pathname);
    }

    const promise = fetch(prefixedUrl.href, {
      ...requestOptions,
      headers: {
        ...headers,
        ...requestOptions.headers,
      },
    });

    promise.then((response) => {
      if (response.headers.has("X-SET-XSRFToken")) {
        const url = URLExt.parse(response.url);
        const xsrfToken = response.headers.get("X-SET-XSRFToken");
        const regex = RegExp(`^\\w+://${url.hostname}`)
        if (xsrfToken !== "") {
          this.setDefaultHeaders(regex, {"X-XSRFToken": xsrfToken});
        }
        else {
          this.clearDefaultHeader(regex, "X-XSRFToken");
        }
      }
    })

    return promise;
  }
}

// Create a default fetch client instance
export const client = new FetchClient();

// Export the fetch method bound to the default instance
const fetchMethod: FetchClient["fetch"] = client.fetch.bind(client);
export {fetchMethod as fetch};
