import React from 'react';
import {
	AbsoluteFill,
	Img,
	useCurrentFrame,
	useVideoConfig,
	interpolate,
	CalculateMetadataFunction,
	staticFile,
	Easing,
	spring,
} from 'remotion';
import {Audio} from '@remotion/media';
import {TransitionSeries, linearTiming, springTiming} from '@remotion/transitions';
import type {TransitionPresentation, TransitionPresentationComponentProps} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import {wipe} from '@remotion/transitions/wipe';
import {clockWipe} from '@remotion/transitions/clock-wipe';
import {iris} from '@remotion/transitions/iris';
import {flip} from '@remotion/transitions/flip';
import {CameraMotionBlur} from '@remotion/motion-blur';
import {evolvePath} from '@remotion/paths';
import {Circle, Star, Heart, Polygon} from '@remotion/shapes';
import {z} from 'zod';
import {zColor} from '@remotion/zod-types';

// ─── Custom Transition: Dissolve (with slight scale, different from plain fade) ───
const DissolvePresentation: React.FC<TransitionPresentationComponentProps<{}>> = ({
	children,
	presentationDirection,
	presentationProgress,
}) => {
	const isEntering = presentationDirection === 'entering';
	const opacity = isEntering ? presentationProgress : 1 - presentationProgress;
	const scale = isEntering
		? interpolate(presentationProgress, [0, 1], [1.05, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(presentationProgress, [0, 1], [1, 1.05], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{opacity, transform: `scale(${scale})`}}>
			{children}
		</AbsoluteFill>
	);
};
const dissolve = (): TransitionPresentation<{}> => ({
	component: DissolvePresentation,
	props: {},
});

// ─── Custom Transition: Zoom ───
const ZoomPresentation: React.FC<TransitionPresentationComponentProps<{direction?: 'in' | 'out'}>> = ({
	children,
	presentationDirection,
	presentationProgress,
	passedProps,
}) => {
	const dir = passedProps.direction || 'in';
	const isEntering = presentationDirection === 'entering';
	let scale: number;
	if (dir === 'in') {
		scale = isEntering
			? interpolate(presentationProgress, [0, 1], [0.3, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
			: interpolate(presentationProgress, [0, 1], [1, 2], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	} else {
		scale = isEntering
			? interpolate(presentationProgress, [0, 1], [2, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
			: interpolate(presentationProgress, [0, 1], [1, 0.3], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	}
	const opacity = isEntering ? presentationProgress : 1 - presentationProgress;
	return (
		<AbsoluteFill style={{opacity, transform: `scale(${scale})`}}>
			{children}
		</AbsoluteFill>
	);
};
const zoom = (props?: {direction?: 'in' | 'out'}): TransitionPresentation<{direction?: 'in' | 'out'}> => ({
	component: ZoomPresentation,
	props: props || {},
});

// ─── Custom Transition: Rotate ───
const RotatePresentation: React.FC<TransitionPresentationComponentProps<{direction?: 'cw' | 'ccw'}>> = ({
	children,
	presentationDirection,
	presentationProgress,
	passedProps,
}) => {
	const dir = passedProps.direction || 'cw';
	const isEntering = presentationDirection === 'entering';
	const angle = dir === 'cw' ? 90 : -90;
	const rotation = isEntering
		? interpolate(presentationProgress, [0, 1], [angle, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(presentationProgress, [0, 1], [0, -angle], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const scale = isEntering
		? interpolate(presentationProgress, [0, 0.5, 1], [0.5, 0.8, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(presentationProgress, [0, 0.5, 1], [1, 0.8, 0.5], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const opacity = isEntering
		? interpolate(presentationProgress, [0, 0.3, 1], [0, 0.5, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(presentationProgress, [0, 0.7, 1], [1, 0.5, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{opacity, transform: `rotate(${rotation}deg) scale(${scale})`}}>
			{children}
		</AbsoluteFill>
	);
};
const rotate = (props?: {direction?: 'cw' | 'ccw'}): TransitionPresentation<{direction?: 'cw' | 'ccw'}> => ({
	component: RotatePresentation,
	props: props || {},
});

// ─── Custom Transition: Blur ───
const BlurPresentation: React.FC<TransitionPresentationComponentProps<{blurAmount?: number}>> = ({
	children,
	presentationDirection,
	presentationProgress,
	passedProps,
}) => {
	const blurPx = passedProps.blurAmount || 30;
	const isEntering = presentationDirection === 'entering';
	const blur = isEntering
		? interpolate(presentationProgress, [0, 1], [blurPx, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(presentationProgress, [0, 1], [0, blurPx], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const opacity = isEntering
		? interpolate(presentationProgress, [0, 0.3, 1], [0, 0.6, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(presentationProgress, [0, 0.7, 1], [1, 0.6, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{opacity, filter: `blur(${blur}px)`}}>
			{children}
		</AbsoluteFill>
	);
};
const blur = (props?: {blurAmount?: number}): TransitionPresentation<{blurAmount?: number}> => ({
	component: BlurPresentation,
	props: props || {},
});

// ─── Custom Transition: Glitch ───
const GlitchPresentation: React.FC<TransitionPresentationComponentProps<{}>> = ({
	children,
	presentationDirection,
	presentationProgress,
}) => {
	const isEntering = presentationDirection === 'entering';
	const p = presentationProgress;
	const glitchPhase = Math.floor(p * 8) % 2;
	const offsetX = glitchPhase === 0 ? interpolate(p, [0, 1], [20, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : interpolate(p, [0, 1], [-15, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const offsetY = glitchPhase === 0 ? interpolate(p, [0, 1], [-5, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : interpolate(p, [0, 1], [8, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const opacity = isEntering
		? interpolate(p, [0, 0.4, 1], [0, 0.8, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})
		: interpolate(p, [0, 0.6, 1], [1, 0.8, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{
			opacity,
			transform: `translate(${offsetX}px, ${offsetY}px)`,
			filter: `saturate(${1 + glitchPhase * 0.5})`,
		}}>
			{children}
		</AbsoluteFill>
	);
};
const glitch = (): TransitionPresentation<{}> => ({
	component: GlitchPresentation,
	props: {},
});

// ─── Zod Schema (parameterized video) ───
export const DecorationItemSchema = z.object({
	shape: z.enum(['circle', 'star', 'heart', 'polygon', 'arrow']),
	position: z.enum(['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']),
	color: zColor(),
	size: z.number(),
	opacity: z.number().optional(),
});

export const TransitionPropsSchema = z.object({
	wipeDirection: z.enum(['from-left', 'from-top-left', 'from-top', 'from-top-right', 'from-right', 'from-bottom-right', 'from-bottom', 'from-bottom-left']).optional(),
	flipDirection: z.enum(['from-left', 'from-right', 'from-top', 'from-bottom']).optional(),
	flipPerspective: z.number().optional(),
	shouldFadeOutExitingScene: z.boolean().optional(),
	slideEnterStyle: z.record(z.string(), z.any()).optional(),
	slideExitStyle: z.record(z.string(), z.any()).optional(),
	zoomDirection: z.enum(['in', 'out']).optional(),
	rotateDirection: z.enum(['cw', 'ccw']).optional(),
	blurAmount: z.number().optional(),
});

export const SceneDataSchema = z.object({
	image: z.string(),
	animation: z.enum(['zoom-in', 'zoom-out', 'pan-left', 'pan-right', 'tilt-up', 'tilt-down', 'rotate-cw', 'rotate-ccw', '3d-tilt-left', '3d-tilt-right', 'static']),
	transition: z.enum(['fade', 'dissolve', 'slide-left', 'slide-right', 'slide-up', 'slide-down', 'wipe', 'clock-wipe', 'iris', 'flip', 'zoom', 'rotate', 'blur', 'glitch', 'none']).optional(),
	transitionDuration: z.number().optional(),
	transitionProps: TransitionPropsSchema.optional(),
	narration: z.string().optional(),
	effect: z.enum(['motion-blur', 'none']).optional(),
	caption: z.string().optional(),
	decorations: z.array(DecorationItemSchema).optional(),

});

export const ThemeColorsSchema = z.object({
	bgColor: zColor().optional(),
	textColor: zColor().optional(),
	accentColor: zColor().optional(),
});

export const VideoPropsSchema = z.object({
	title: z.string(),
	subtitle: z.string(),
	endText: z.string(),
	scenes: z.array(SceneDataSchema),
	sceneDurations: z.array(z.number()).optional(),
	totalFrames: z.number().optional(),
	bgmSrc: z.string().optional(),
	titleStroke: z.boolean().optional(),
	theme: ThemeColorsSchema.optional(),
	resolution: z.enum(['landscape', 'portrait']).optional(),
});

// ─── Types (inferred from Zod) ───
export type DecorationItem = z.infer<typeof DecorationItemSchema>;
export type TransitionProps = z.infer<typeof TransitionPropsSchema>;
export type SceneData = z.infer<typeof SceneDataSchema>;
export type ThemeColors = z.infer<typeof ThemeColorsSchema>;
export type VideoProps = z.infer<typeof VideoPropsSchema>;



const defaultTheme: ThemeColors = {
	bgColor: '#1a1a2e',
	textColor: '#e8d5b7',
	accentColor: '#a89070',
};


const FPS = 24;
const TITLE_FRAMES = 90;
const END_FRAMES = 90;
const BUFFER_FRAMES = 15;
const TRANSITION_FRAMES = 18;

export const calculateMetadata: CalculateMetadataFunction<VideoProps> = async ({props}) => {
	const scenes = props.scenes || [];
	if (scenes.length === 0) return {durationInFrames: 300, props};

	const sceneDurations: number[] = props.sceneDurations?.length === scenes.length
		? props.sceneDurations
		: scenes.map(() => 5 * FPS + BUFFER_FRAMES);

	// Use timing.getDurationInFrames() per Remotion best practices
	const titleTransitionFrames = linearTiming({durationInFrames: TRANSITION_FRAMES}).getDurationInFrames({fps: FPS});
	const totalTransitionFrames = titleTransitionFrames + (scenes.length > 1
		? scenes.slice(0, -1).reduce((sum, s) => {
			if (s.transition === 'none') return sum;
			const dur = s.transitionDuration || TRANSITION_FRAMES;
			return sum + linearTiming({durationInFrames: dur}).getDurationInFrames({fps: FPS});
		}, 0)
		: 0);

	// Also account for the end fade transition
	const endTransitionFrames = linearTiming({durationInFrames: TRANSITION_FRAMES}).getDurationInFrames({fps: FPS});
	const totalFrames = TITLE_FRAMES + sceneDurations.reduce((a, b) => a + b, 0) - totalTransitionFrames - endTransitionFrames + END_FRAMES;
	// Resolution: landscape=1280x720, portrait=720x1280
	const isPortrait = props.resolution === 'portrait';

	return {
		durationInFrames: totalFrames,
		width: isPortrait ? 720 : 1280,
		height: isPortrait ? 1280 : 720,
		props: {...props, sceneDurations, totalFrames},
	};
};

const kenBurnsEasing = Easing.bezier(0.25, 0.1, 0.25, 1.0);

const getKenBurnsTransform = (animation: string, frame: number, durationInFrames: number) => {
	const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: kenBurnsEasing,
	});
	switch (animation) {
		case 'zoom-in': return {scale: interpolate(progress, [0, 1], [1, 1.3], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translateX: 0, translateY: 0, rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
		case 'zoom-out': return {scale: interpolate(progress, [0, 1], [1.3, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translateX: 0, translateY: 0, rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
		case 'pan-left': return {scale: 1.18, translateX: interpolate(progress, [0, 1], [150, -150], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translateY: 0, rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
		case 'pan-right': return {scale: 1.18, translateX: interpolate(progress, [0, 1], [-150, 150], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translateY: 0, rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
		case 'tilt-up': return {scale: 1.18, translateX: 0, translateY: interpolate(progress, [0, 1], [100, -100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
		case 'tilt-down': return {scale: 1.18, translateX: 0, translateY: interpolate(progress, [0, 1], [-100, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
		case 'rotate-cw': return {scale: 1.18, translateX: 0, translateY: 0, rotate: interpolate(progress, [0, 1], [0, 15], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), perspective: '', rotateX: 0, rotateY: 0};
		case 'rotate-ccw': return {scale: 1.18, translateX: 0, translateY: 0, rotate: interpolate(progress, [0, 1], [0, -15], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), perspective: '', rotateX: 0, rotateY: 0};
		case '3d-tilt-left': return {scale: 1.1, translateX: interpolate(progress, [0, 1], [30, -30], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translateY: 0, rotate: 0, perspective: 'perspective(1000px)', rotateX: 0, rotateY: interpolate(progress, [0, 1], [5, -5], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})};
		case '3d-tilt-right': return {scale: 1.1, translateX: interpolate(progress, [0, 1], [-30, 30], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translateY: 0, rotate: 0, perspective: 'perspective(1000px)', rotateX: 0, rotateY: interpolate(progress, [0, 1], [-5, 5], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})};
		case 'static': return {
			scale: interpolate(progress, [0, 0.25, 0.5, 0.75, 1], [1, 1.02, 1, 0.98, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
			translateX: interpolate(progress, [0, 0.33, 0.67, 1], [0, 5, -5, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
			translateY: interpolate(progress, [0, 0.33, 0.67, 1], [0, -3, 3, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
			rotate: 0, perspective: '', rotateX: 0, rotateY: 0
		};
		default: return {scale: 1, translateX: 0, translateY: 0, rotate: 0, perspective: '', rotateX: 0, rotateY: 0};
	}
};

// Map transition name + props to Remotion presentation
const getTransitionPresentation = (transition: string | undefined, width: number = 1280, height: number = 720, tProps?: TransitionProps) => {
	switch (transition || 'fade') {
		case 'fade': return fade({shouldFadeOutExitingScene: tProps?.shouldFadeOutExitingScene ?? true});
		case 'dissolve': return dissolve();
		case 'slide-left': return slide({direction: 'from-right', enterStyle: tProps?.slideEnterStyle, exitStyle: tProps?.slideExitStyle});
		case 'slide-right': return slide({direction: 'from-left', enterStyle: tProps?.slideEnterStyle, exitStyle: tProps?.slideExitStyle});
		case 'slide-up': return slide({direction: 'from-bottom', enterStyle: tProps?.slideEnterStyle, exitStyle: tProps?.slideExitStyle});
		case 'slide-down': return slide({direction: 'from-top', enterStyle: tProps?.slideEnterStyle, exitStyle: tProps?.slideExitStyle});
		case 'wipe': return wipe({direction: tProps?.wipeDirection || 'from-left', outerEnterStyle: tProps?.slideEnterStyle, outerExitStyle: tProps?.slideExitStyle, innerEnterStyle: tProps?.slideEnterStyle, innerExitStyle: tProps?.slideExitStyle});
		case 'clock-wipe': return clockWipe({width, height, outerEnterStyle: tProps?.slideEnterStyle, outerExitStyle: tProps?.slideExitStyle, innerEnterStyle: tProps?.slideEnterStyle, innerExitStyle: tProps?.slideExitStyle});
		case 'iris': return iris({width, height, outerEnterStyle: tProps?.slideEnterStyle, outerExitStyle: tProps?.slideExitStyle, innerEnterStyle: tProps?.slideEnterStyle, innerExitStyle: tProps?.slideExitStyle});
		case 'flip': return flip({direction: tProps?.flipDirection || 'from-left', perspective: tProps?.flipPerspective || 1000, outerEnterStyle: tProps?.slideEnterStyle, outerExitStyle: tProps?.slideExitStyle, innerEnterStyle: tProps?.slideEnterStyle, innerExitStyle: tProps?.slideExitStyle});
		case 'zoom': return zoom({direction: tProps?.zoomDirection || 'in'});
		case 'rotate': return rotate({direction: tProps?.rotateDirection || 'cw'});
		case 'blur': return blur({blurAmount: tProps?.blurAmount || 30});
		case 'glitch': return glitch();
		case 'none': return null;
		default: return fade();
	}
};

// ─── Effect: Caption Overlay ───
const CaptionOverlay: React.FC<{text: string}> = ({text}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const opacity = interpolate(frame, [0, 15, durationInFrames - 15, durationInFrames], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 60, opacity}}>
			<div style={{
				backgroundColor: 'rgba(0,0,0,0.6)',
				padding: '8px 24px',
				borderRadius: 8,
				maxWidth: '80%',
			}}>
				<span style={{color: '#fff', fontSize: 28, fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif', fontWeight: 600, textShadow: '0 2px 4px rgba(0,0,0,0.5)'}}>{text}</span>
			</div>
		</AbsoluteFill>
	);
};

// ─── Effect: Geometric Decorations ───
const positionToStyle = (pos: string, size: number): React.CSSProperties => {
	const margin = 30;
	switch (pos) {
		case 'top-left': return {top: margin, left: margin};
		case 'top-right': return {top: margin, right: margin};
		case 'bottom-left': return {bottom: margin + 50, left: margin};
		case 'bottom-right': return {bottom: margin + 50, right: margin};
		case 'center': return {top: `calc(50% - ${size / 2}px)`, left: `calc(50% - ${size / 2}px)`};
		default: return {top: margin, left: margin};
	}
};

const ShapeRenderer: React.FC<{item: DecorationItem}> = ({item}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const scale = spring({frame, fps, config: {damping: 12, stiffness: 80}});
	const opacity = item.opacity ?? 0.6;
	const posStyle = positionToStyle(item.position, item.size);
	const svgStyle: React.CSSProperties = {opacity: opacity * scale, width: item.size, height: item.size};

	return (
		<AbsoluteFill style={{...posStyle, position: 'absolute', transform: `scale(${scale})`}}>
			{item.shape === 'circle' && <Circle radius={item.size / 2} fill={item.color} style={svgStyle} />}
			{item.shape === 'star' && <Star points={5} innerRadius={item.size * 0.4} outerRadius={item.size / 2} fill={item.color} style={svgStyle} />}
			{item.shape === 'heart' && <Heart height={item.size} fill={item.color} style={svgStyle} />}
			{item.shape === 'polygon' && <Polygon points={6} radius={item.size / 2} cornerRadius={0} edgeRoundness={null} fill={item.color} style={svgStyle} />}
			{item.shape === 'arrow' && <svg width={item.size} height={item.size} viewBox="0 0 24 24" fill={item.color} style={svgStyle}><path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z"/></svg>}
		</AbsoluteFill>
	);
};

// ─── Ken Burns Image (separate component so CameraMotionBlur can track frame changes) ───
const KenBurnsImage: React.FC<{image: string; animation: string; sceneDuration: number; transitionDuration?: number; transition?: string}> = ({image, animation, sceneDuration, transitionDuration, transition}) => {
	const frame = useCurrentFrame();
	const kb = getKenBurnsTransform(animation, frame, sceneDuration);

	// 修复残影：退出场景在转场开始时 opacity 直接跳 0，避免与进入场景半透明叠加
	// fade/dissolve/blur 类转场中间帧两张图同时半透明，退出场景透过来形成残影
	const transDur = transitionDuration || TRANSITION_FRAMES;
	const opacity = (transition && transition !== 'none' && frame >= sceneDuration - transDur) ? 0 : 1;

	const transformParts = [
		kb.perspective ? kb.perspective : '',
		`scale(${kb.scale})`,
		`translate(${kb.translateX}px, ${kb.translateY}px)`,
		kb.rotate ? `rotate(${kb.rotate}deg)` : '',
		kb.rotateX ? `rotateX(${kb.rotateX}deg)` : '',
		kb.rotateY ? `rotateY(${kb.rotateY}deg)` : '',
	].filter(Boolean).join(' ');

	return (
		<AbsoluteFill style={{
			backgroundColor: '#000',
			display: 'flex',
			justifyContent: 'center',
			alignItems: 'center',
			transform: transformParts,
			opacity,
		}}>
			<Img src={staticFile(`images/${image}`)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
		</AbsoluteFill>
	);
};

// ─── SVG Stroke Grow (描边生长装饰) ───
const StrokeGrow: React.FC<{path: string; color: string; strokeWidth?: number; duration?: number; position?: React.CSSProperties; viewBox?: string}> = ({path, color, strokeWidth = 2, duration = 60, position, viewBox}) => {
	const frame = useCurrentFrame();
	const progress = interpolate(frame, [0, duration], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const {strokeDasharray, strokeDashoffset} = evolvePath(progress, path);

	return (
		<svg style={{position: 'absolute', ...position, pointerEvents: 'none', overflow: 'visible'}} viewBox={viewBox || '0 0 1280 720'}>
			<path
				d={path}
				stroke={color}
				strokeWidth={strokeWidth}
				fill="none"
				strokeDasharray={strokeDasharray}
				strokeDashoffset={strokeDashoffset}
				strokeLinecap="round"
				opacity={0.4}
			/>
		</svg>
	);
};

// ─── Vignette Overlay ───
const VignetteOverlay: React.FC<{strength?: number}> = ({strength = 0.2}) => {
	return (
		<AbsoluteFill style={{
			background: `radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,${strength}) 100%)`,
			pointerEvents: 'none',
		}} />
	);
};

// ─── Color Grade Overlay ───
const ColorGradeOverlay: React.FC<{theme?: ThemeColors}> = ({theme}) => {
	// 根据主题色调加轻微色彩叠加，统一画面色调
	const colorMap: Record<string, string> = {
		'#1a1a2e': 'rgba(20, 10, 40, 0.08)',
		'#2d1b0e': 'rgba(60, 30, 0, 0.1)',
		'#0a1628': 'rgba(0, 20, 60, 0.1)',
		'#0d2818': 'rgba(0, 40, 20, 0.08)',
		'#2d0a1e': 'rgba(50, 0, 30, 0.08)',
		'#0a0a0a': 'rgba(0, 30, 15, 0.06)',
	};
	const bgColor = theme?.bgColor || '#1a1a2e';
	const grade = colorMap[bgColor] || colorMap['#1a1a2e'];
	return (
		<AbsoluteFill style={{
			background: grade,
			pointerEvents: 'none',
			mixBlendMode: 'overlay',
		}} />
	);
};

// ─── Scene Component ───
const Scene: React.FC<{scene: SceneData; sceneDuration: number; theme?: ThemeColors}> = ({scene, sceneDuration, theme}) => {
	const imageElement = <KenBurnsImage image={scene.image} animation={scene.animation} sceneDuration={sceneDuration} transitionDuration={scene.transitionDuration} transition={scene.transition} />;

	// 快速运动动画或显式 motion-blur 效果时启用 CameraMotionBlur
	const needsMotionBlur = scene.effect === 'motion-blur';

	const wrappedImage = needsMotionBlur ? (
		<CameraMotionBlur shutterAngle={180} samples={4}>
			{imageElement}
		</CameraMotionBlur>
	) : imageElement;

	return (
		<AbsoluteFill style={{backgroundColor: '#000'}}>
			{wrappedImage}
			{/* Vignette 和 ColorGrade 仅在有 caption 或 decorations 时启用，
				避免在纯图片场景叠加半透明黑色层形成"黑色框框"效果。 */}
			{scene.caption && <VignetteOverlay strength={0.15} />}
			{scene.decorations && scene.decorations.length > 0 && <ColorGradeOverlay theme={theme} />}
			{scene.caption && <AbsoluteFill style={{
				background: 'linear-gradient(to top, rgba(0,0,0,0.5) 0%, transparent 30%)',
				bottom: 0,
				height: '25%',
				top: undefined,
			}} />}
				{scene.caption && <CaptionOverlay text={scene.caption} />}
			{scene.decorations?.map((dec, i) => <ShapeRenderer key={`dec-${i}`} item={dec} />)}
		</AbsoluteFill>
	);
};

// ─── Title Card with optional SVG stroke ───
const TitleCard: React.FC<{title: string; subtitle: string; titleStroke?: boolean; theme: ThemeColors; videoWidth?: number; videoHeight?: number}> = ({title, subtitle, titleStroke, theme, videoWidth, videoHeight}) => {
	const bgColor = theme.bgColor || defaultTheme.bgColor!;
	const textColor = theme.textColor || defaultTheme.textColor!;
	const accentColor = theme.accentColor || defaultTheme.accentColor!;

	const frame = useCurrentFrame();
	const tOp = interpolate(frame, [0, 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const sOp = interpolate(frame, [15, 35], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const fadeOut = interpolate(frame, [70, 90], [1, 0], {extrapolateLeft: 'clamp'});
	const scale = interpolate(frame, [0, 30], [0.9, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});

	// SVG stroke dash animation
	const strokeProgress = titleStroke ? interpolate(frame, [10, 70], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;

	return (
		<AbsoluteFill style={{backgroundColor: bgColor, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', opacity: Math.min(tOp, fadeOut)}}>
			<div style={{
				fontSize: 60,
				fontWeight: 'normal',
				color: titleStroke ? 'transparent' : textColor,
				fontFamily: '"Georgia", "Times New Roman", serif',
				letterSpacing: 8,
				transform: `scale(${scale})`,
				WebkitTextStroke: titleStroke && strokeProgress < 1 ? `1px ${textColor}` : undefined,
				clipPath: titleStroke ? `inset(0 ${interpolate(strokeProgress, [0, 1], [100, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}% 0 0)` : undefined,
			}}>{title}</div>
			<div style={{fontSize: 24, color: accentColor, marginTop: 20, opacity: sOp, fontFamily: '"Georgia", "Times New Roman", serif', letterSpacing: 4}}>{subtitle}</div>
			<StrokeGrow
				path="M 540 420 Q 640 440 740 420"
				color={accentColor}
				strokeWidth={1.5}
				duration={50}
				position={{top: 0, left: 0, width: '100%', height: '100%'}}
				viewBox={`0 0 ${videoWidth || 1280} ${videoHeight || 720}`}
			/>
		</AbsoluteFill>
	);
};

const EndCard: React.FC<{text: string; theme: ThemeColors}> = ({text, theme}) => {
	const bgColor = theme.bgColor || defaultTheme.bgColor!;
	const textColor = theme.textColor || defaultTheme.textColor!;
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const scale = interpolate(frame, [0, 30], [0.9, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
	return (
		<AbsoluteFill style={{backgroundColor: bgColor, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', opacity}}>
			<div style={{fontSize: 36, color: textColor, fontFamily: '"Georgia", "Times New Roman", serif', letterSpacing: 4, transform: `scale(${scale})`}}>{text}</div>
		</AbsoluteFill>
	);
};

export const MainComposition: React.FC<VideoProps> = (rawProps) => {
	const {title, subtitle, endText, scenes, sceneDurations, bgmSrc, titleStroke, theme: rawTheme, totalFrames: rawTotalFrames} = rawProps;
	const theme = {...defaultTheme, ...rawTheme};
	const {width: videoWidth, height: videoHeight} = useVideoConfig();

	if (!scenes || scenes.length === 0) {
		return <AbsoluteFill style={{backgroundColor: '#000'}} />;
	}

	const totalFrames = rawTotalFrames || 300;

	const children: React.ReactNode[] = [];

	children.push(
		<TransitionSeries.Sequence key="title" durationInFrames={TITLE_FRAMES} premountFor={FPS}>
			<TitleCard title={title} subtitle={subtitle} titleStroke={titleStroke} theme={theme} videoWidth={videoWidth} videoHeight={videoHeight} />
		</TransitionSeries.Sequence>
	);

	children.push(
		<TransitionSeries.Transition
			key="trans-title"
			presentation={fade()}
			timing={linearTiming({durationInFrames: TRANSITION_FRAMES})}
		/>
	);

	scenes.forEach((scene, i) => {
		const duration = sceneDurations?.[i] || 150;

		children.push(
			<TransitionSeries.Sequence key={`scene-${i}`} durationInFrames={duration} premountFor={FPS}>
				<Scene scene={scene} sceneDuration={duration} theme={theme} />
			</TransitionSeries.Sequence>
		);

		if (i < scenes.length - 1) {
			const presentation = getTransitionPresentation(scene.transition, videoWidth, videoHeight, scene.transitionProps);
			if (presentation) {
				children.push(
					<TransitionSeries.Transition
						key={`trans-${i}`}
						presentation={presentation}
						timing={linearTiming({durationInFrames: scene.transitionDuration || TRANSITION_FRAMES})}
					/>
				);
			}
		}
	});

	children.push(
		<TransitionSeries.Transition
			key="trans-end"
			presentation={fade()}
			timing={linearTiming({durationInFrames: TRANSITION_FRAMES})}
		/>
	);

	children.push(
		<TransitionSeries.Sequence key="end" durationInFrames={END_FRAMES} premountFor={FPS}>
			<EndCard text={endText} theme={theme} />
		</TransitionSeries.Sequence>
	);

	const bgmAudio = bgmSrc ? (
		<Audio
			src={staticFile(`audio/${bgmSrc}`)}
			loop
			loopVolumeCurveBehavior="extend"
			volume={(f) => {
				const fadeIn = interpolate(f, [0, FPS * 2], [0, 0.8], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
				const fadeOutStart = totalFrames - 1 * FPS;
				if (f >= fadeOutStart) {
					return interpolate(f, [fadeOutStart, totalFrames], [0.8, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
				}
				return fadeIn;
			}}
			trimAfter={totalFrames}
		/>
	) : null;

	return (
		<AbsoluteFill style={{backgroundColor: '#000'}}>
			<TransitionSeries>
				{children}
			</TransitionSeries>
			{bgmAudio}
		</AbsoluteFill>
	);
};