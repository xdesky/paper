export type Project = {id:string;name:string;preset:string;paper:'US Letter'|'A4';revision:number;status:string;result_revision:number|null};
export type Panel = {id:string;face:string;vertices_3d_mm:number[][];polygon_mm?:number[][];width_mm?:number;height_mm?:number};
export type Seam = {id:string;mates:{panel:string;edge:string}[];hinged_uncut:boolean;fold_degrees:number};
export type Spec = {model_id:string;version:string;geometry_sha256:string;sheet_count:number;appearance?:{panels:Record<string,string>};geometry:{model:Record<string,unknown>;panels:Panel[];seams:Seam[]}};
export type QA = {overall_status:string;tests:{name:string;status:string;detail:unknown}[];summary:{sheets:number;cut_pieces:number;fold_hinges:number;glue_seams:number;flat_continuous_joins:number}};
export type Job = {id:string;stage:string;status:string;error:string|null};
