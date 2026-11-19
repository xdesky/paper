type Props={label:string;off:string;on:string;checked:boolean;onChange:(checked:boolean)=>void;disabled?:boolean};
export function BinarySwitch({label,off,on,checked,onChange,disabled}:Props){
 return <div className="binary-field"><span className="binary-label">{label}</span><div className="binary-options"><span className={!checked?'is-current':''}>{off}</span><button type="button" role="switch" aria-label={label} aria-checked={checked} disabled={disabled} onClick={()=>onChange(!checked)} className="binary-switch"><span/></button><span className={checked?'is-current':''}>{on}</span></div></div>;
}
