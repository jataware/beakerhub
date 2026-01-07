import { URLExt } from '@jupyterlab/coreutils';

type DefaultHeaders = Record<string, HeadersInit>;

class FetchClient {
  private defaultHeaders: DefaultHeaders;

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

  async fetch(url: string, options?: RequestInit): Promise<Response> {
    const headers = this.headersForUrl(url);

    const promise = fetch(url, {
      ...options,
      headers: {
        ...headers,
        ...options?.headers,
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
