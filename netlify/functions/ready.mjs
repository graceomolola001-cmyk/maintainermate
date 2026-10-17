import {createApi} from '../lib/api.mjs';
const handle = createApi();
export default request => handle(request, 'ready');
export const config = {path: '/ready'};
