(() => {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const root = document.documentElement;
        const body = document.body;
        const stage = document.querySelector('[data-home-parallax]');
        const hero = stage?.querySelector('[data-home-parallax-hero]');
        const background = stage?.querySelector('.home-hero-photo-background');
        const scenes = Array.from(document.querySelectorAll('[data-home-scene]'));
        const sceneLinks = Array.from(document.querySelectorAll('[data-home-scene-link]'));
        const sceneChapters = Array.from(document.querySelectorAll('[data-home-scene-chapter]'));
        const footer = document.querySelector('.page-homepage .site-footer');
        const handoffAnchors = new Map(
            Array.from(document.querySelectorAll('[data-home-handoff-anchor]'))
                .map((anchor) => [anchor.dataset.homeHandoffAnchor, anchor]),
        );

        if (!stage || !hero || !background || !scenes.length) return;

        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        const mobileLayout = window.matchMedia('(max-width: 640px)');
        const snapLayout = window.matchMedia('(min-width: 1024px) and (min-height: 640px)');
        const SNAP_TRAVEL_DURATION = 850;
        const SNAP_LONG_TRAVEL_MAX = 1150;
        const SNAP_WHEEL_THRESHOLD = 18;
        const SNAP_MOMENTUM_COOLDOWN = 180;
        const handoffs = [
            { from: 'hero-heart', fromScene: 0, to: 'courses-heart', toScene: 1 },
            { from: 'courses-gallbladder', fromScene: 1, to: 'sleep-gallbladder', toScene: 2 },
        ];
        const organClipPaths = {
            'hero-heart': 'url("#home-clip-heart-hero")',
            'courses-heart': 'url("#home-clip-heart-courses")',
            'courses-gallbladder': 'url("#home-clip-gallbladder-courses")',
            'sleep-gallbladder': 'url("#home-clip-gallbladder-sleep")',
        };
        const handoffElement = document.createElement('div');
        const handoffSource = document.createElement('span');
        const handoffTarget = document.createElement('span');
        let activeHandoffKey = '';
        let activeSceneName = '';
        let depthStates = [];
        let handoffSnapshots = new Map();
        let parallaxStyleKey = '';
        let parallaxGeometry = null;
        let sceneStops = [];
        let snapStops = [];
        let storyHeaderHeight = 0;
        let updateFrame = null;
        let resizeFrame = null;
        let snapAnimationFrame = null;
        let snapIsAnimating = false;
        let snapCooldownUntil = 0;
        let wheelDelta = 0;
        let wheelResetTimer = null;

        handoffElement.className = 'home-object-handoff';
        handoffElement.dataset.homeObjectHandoff = '';
        handoffElement.setAttribute('aria-hidden', 'true');
        handoffSource.className = 'home-object-handoff__image home-object-handoff__image--source';
        handoffTarget.className = 'home-object-handoff__image home-object-handoff__image--target';
        handoffElement.append(handoffSource, handoffTarget);
        body.append(handoffElement);

        const clamp = (value, minimum = 0, maximum = 1) => Math.min(maximum, Math.max(minimum, value));
        const lerp = (start, end, progress) => start + ((end - start) * progress);
        const smoothstep = (start, end, value) => {
            const progress = clamp((value - start) / (end - start));
            return progress * progress * (3 - (2 * progress));
        };
        const format = (value) => Number(value.toFixed(3));
        const easeInOutSine = (progress) => -(Math.cos(Math.PI * progress) - 1) / 2;

        const snapIsEnabled = () => snapLayout.matches && !reducedMotion.matches;

        const enterFooter = () => {
            if (!footer) return;
            root.classList.add('home-footer-scroll');
            window.scrollTo({
                behavior: reducedMotion.matches ? 'auto' : 'smooth',
                top: document.documentElement.scrollHeight,
            });
        };

        const imagePositionRatio = (value) => {
            if (value === 'left' || value === 'top') return 0;
            if (value === 'right' || value === 'bottom') return 1;
            if (value === 'center') return 0.5;
            const percentage = Number.parseFloat(value);
            return Number.isFinite(percentage) ? percentage / 100 : 0.5;
        };

        const measureAnchorSnapshot = (name) => {
            const anchor = handoffAnchors.get(name);
            const media = anchor?.closest('.home-hero-media, .home-feature-media');
            const image = media?.querySelector('.home-hero-photo-fallback, img');
            if (!anchor || !media || !image) return null;

            const mediaRect = media.getBoundingClientRect();
            const sourceWidth = image.naturalWidth || Number(image.getAttribute('width'));
            const sourceHeight = image.naturalHeight || Number(image.getAttribute('height'));
            if (!sourceWidth || !sourceHeight || !mediaRect.width || !mediaRect.height) return null;

            const computedImage = window.getComputedStyle(image);
            const [positionX = '50%', positionY = '50%'] = computedImage.objectPosition.split(' ');
            const scale = Math.max(mediaRect.width / sourceWidth, mediaRect.height / sourceHeight);
            const renderedWidth = sourceWidth * scale;
            const renderedHeight = sourceHeight * scale;
            const offsetX = (mediaRect.width - renderedWidth) * imagePositionRatio(positionX);
            const offsetY = (mediaRect.height - renderedHeight) * imagePositionRatio(positionY);
            const sourceX = Number(anchor.dataset.organSourceX);
            const sourceY = Number(anchor.dataset.organSourceY);
            const renderedSize = Number(anchor.dataset.organSourceSize) * scale;
            const cropSize = Math.max(72, renderedSize * 1.08);

            return {
                backgroundImage: `url("${image.currentSrc || image.src}")`,
                backgroundSize: `${format(renderedWidth)}px ${format(renderedHeight)}px`,
                centerX: mediaRect.left + offsetX + (sourceX * scale),
                centerY: mediaRect.top + window.scrollY + offsetY + (sourceY * scale),
                clipPath: organClipPaths[name],
                scaledSourceX: sourceX * scale,
                scaledSourceY: sourceY * scale,
                size: cropSize,
            };
        };

        const configureSnapshot = (element, snapshot) => {
            element.style.backgroundImage = snapshot.backgroundImage;
            element.style.backgroundPosition = `${format((snapshot.size / 2) - snapshot.scaledSourceX)}px ${format((snapshot.size / 2) - snapshot.scaledSourceY)}px`;
            element.style.backgroundSize = snapshot.backgroundSize;
            element.style.clipPath = snapshot.clipPath;
            element.style.height = `${format(snapshot.size)}px`;
            element.style.left = `${format(snapshot.size / -2)}px`;
            element.style.top = `${format(snapshot.size / -2)}px`;
            element.style.webkitClipPath = snapshot.clipPath;
            element.style.width = `${format(snapshot.size)}px`;
        };

        const hideHandoff = () => {
            activeHandoffKey = '';
            handoffElement.classList.remove('is-visible');
            handoffElement.style.opacity = '0';
        };

        const renderHandoff = () => {
            if (!snapLayout.matches || reducedMotion.matches) {
                hideHandoff();
                return;
            }

            const scrollPosition = window.scrollY;
            const transition = handoffs.find(({ fromScene, toScene }) => (
                scrollPosition > sceneStops[fromScene] + 2
                && scrollPosition < sceneStops[toScene] - 2
            ));
            if (!transition) {
                hideHandoff();
                return;
            }

            const source = handoffSnapshots.get(transition.from);
            const target = handoffSnapshots.get(transition.to);
            if (!source || !target) {
                hideHandoff();
                return;
            }

            const rawProgress = clamp(
                (scrollPosition - sceneStops[transition.fromScene])
                / Math.max(1, sceneStops[transition.toScene] - sceneStops[transition.fromScene]),
            );
            const progress = rawProgress;
            const visibility = Math.sin(Math.PI * progress);
            const crossfade = smoothstep(0.3, 0.7, progress);
            const arc = Math.sin(Math.PI * progress) * Math.min(54, window.innerHeight * 0.07);
            const baseSize = lerp(source.size, target.size, progress);
            const size = baseSize * (1 + (Math.sin(Math.PI * progress) * 0.045));
            const centerX = lerp(source.centerX, target.centerX, progress);
            const centerY = lerp(source.centerY, target.centerY, progress) - scrollPosition - arc;

            const handoffKey = `${transition.from}:${transition.to}`;
            if (handoffKey !== activeHandoffKey) {
                configureSnapshot(handoffSource, source);
                configureSnapshot(handoffTarget, target);
                activeHandoffKey = handoffKey;
            }
            handoffSource.style.opacity = String(format(1 - crossfade));
            handoffSource.style.transform = `scale(${format(size / source.size)})`;
            handoffTarget.style.opacity = String(format(crossfade));
            handoffTarget.style.transform = `scale(${format(size / target.size)})`;
            handoffElement.style.opacity = String(format(visibility));
            handoffElement.style.transform = [
                `translate3d(${format(centerX)}px, ${format(centerY)}px, 0)`,
                `rotate(${format(lerp(-1.4, 1.4, progress))}deg)`,
            ].join(' ');
            handoffElement.classList.add('is-visible');
        };

        const resetDepth = () => {
            depthStates = [];
            scenes.forEach((scene) => {
                scene.classList.remove('home-depth-scene');
                scene.style.removeProperty('--home-depth-blur');
                scene.style.removeProperty('--home-depth-opacity');
                scene.style.removeProperty('--home-depth-photo-scale');
                scene.style.removeProperty('--home-depth-scale');
                scene.style.removeProperty('--home-depth-y');
                scene.style.removeProperty('--home-focus-progress');
                scene.style.removeProperty('--home-focus-photo-scale');
                scene.style.removeProperty('--home-focus-inset');
                scene.style.removeProperty('--home-focus-offset');
                scene.style.removeProperty('--home-focus-offset-negative');
                scene.style.removeProperty('--home-focus-blur');
            });
        };

        const renderDepth = () => {
            if (!snapLayout.matches || reducedMotion.matches) {
                resetDepth();
                return;
            }

            const stageHeight = Math.max(1, window.innerHeight - storyHeaderHeight);
            scenes.forEach((scene, index) => {
                if (index < 2) return;
                const position = (sceneStops[index] - window.scrollY) / stageHeight;
                const depth = index === 2 && position > 0 ? 0 : clamp(Math.abs(position));
                const direction = position > 0 ? 1 : -1;
                const focusValue = smoothstep(0.08, 0.92, 1 - position);
                const focusProgress = String(format(focusValue));
                const focusPhotoScale = String(format(0.975 + (focusValue * 0.025)));
                const focusInset = `${format((1 - focusValue) * 4)}%`;
                const focusOffset = `${format((1 - focusValue) * 32)}px`;
                const focusOffsetNegative = `${format((1 - focusValue) * -32)}px`;
                const focusBlur = `${format((1 - focusValue) * 4)}px`;
                const blur = `${format(depth * 2.2)}px`;
                const opacity = String(format(1 - (depth * 0.2)));
                const photoScale = String(format(1 + (depth * 0.035)));
                const scale = String(format(1 - (depth * 0.045)));
                const translateY = `${format(direction * depth * 22)}px`;
                const state = [blur, opacity, photoScale, scale, translateY, focusProgress].join(':');
                if (depthStates[index] === state) return;

                scene.classList.add('home-depth-scene');
                scene.style.setProperty('--home-depth-blur', blur);
                scene.style.setProperty('--home-depth-opacity', opacity);
                scene.style.setProperty('--home-depth-photo-scale', photoScale);
                scene.style.setProperty('--home-depth-scale', scale);
                scene.style.setProperty('--home-depth-y', translateY);
                scene.style.setProperty('--home-focus-progress', focusProgress);
                scene.style.setProperty('--home-focus-photo-scale', focusPhotoScale);
                scene.style.setProperty('--home-focus-inset', focusInset);
                scene.style.setProperty('--home-focus-offset', focusOffset);
                scene.style.setProperty('--home-focus-offset-negative', focusOffsetNegative);
                scene.style.setProperty('--home-focus-blur', focusBlur);
                depthStates[index] = state;
            });
        };

        const setActiveScene = () => {
            const anchor = Math.min(window.innerHeight * 0.46, 460);
            const readingPosition = window.scrollY + anchor;
            let currentScene = scenes[0];
            sceneStops.forEach((stop, index) => {
                if (stop <= readingPosition) currentScene = scenes[index];
            });

            const sceneName = currentScene.dataset.homeScene || '';
            if (!sceneName || sceneName === activeSceneName) return;
            activeSceneName = sceneName;
            scenes.forEach((scene) => scene.classList.toggle('is-scene-current', scene === currentScene));
            currentScene.classList.add('is-scene-seen');
            sceneLinks.forEach((link) => {
                const isCurrent = link.dataset.homeSceneLink === sceneName;
                link.classList.toggle('is-current', isCurrent);
                if (isCurrent) link.setAttribute('aria-current', 'location');
                else link.removeAttribute('aria-current');
            });
            sceneChapters.forEach((chapter) => {
                const containsCurrentScene = Boolean(chapter.querySelector(`[data-home-scene-link="${sceneName}"]`));
                chapter.classList.toggle('is-current', containsCurrentScene);
            });

            body.classList.remove(...Array.from(body.classList).filter((name) => name.startsWith('home-motion-scene-')));
            body.classList.add(`home-motion-scene-${sceneName}`);
        };

        const setFooterVisibility = () => {
            const footerIsVisible = Boolean(footer && footer.getBoundingClientRect().top < window.innerHeight - 24);
            root.classList.toggle('home-footer-visible', footerIsVisible);
            const finalStop = snapStops.at(-1);
            if (!footerIsVisible && Number.isFinite(finalStop) && window.scrollY <= finalStop + 2) {
                root.classList.remove('home-footer-scroll');
            }
        };

        const measure = () => {
            storyHeaderHeight = document.querySelector('[data-site-header]')?.getBoundingClientRect().height || 0;
            sceneStops = scenes.map((scene, index) => (
                index === 0 ? 0 : Math.max(0, scene.getBoundingClientRect().top + window.scrollY - storyHeaderHeight)
            ));
            snapStops = [...sceneStops];
            handoffSnapshots = new Map(
                Array.from(handoffAnchors.keys())
                    .map((name) => [name, measureAnchorSnapshot(name)])
                    .filter(([, snapshot]) => snapshot),
            );
            const rect = hero.getBoundingClientRect();
            const start = window.scrollY + rect.top;
            parallaxGeometry = {
                end: start + Math.max(hero.offsetHeight * 0.86, window.innerHeight * 0.7),
                start,
            };
        };

        const nearestSnapIndex = () => {
            let nearestIndex = 0;
            let nearestDistance = Number.POSITIVE_INFINITY;
            snapStops.forEach((stop, index) => {
                const distance = Math.abs(window.scrollY - stop);
                if (distance < nearestDistance) {
                    nearestIndex = index;
                    nearestDistance = distance;
                }
            });
            return nearestIndex;
        };

        const cancelSnapTravel = () => {
            if (snapAnimationFrame) window.cancelAnimationFrame(snapAnimationFrame);
            snapAnimationFrame = null;
            snapIsAnimating = false;
            root.classList.remove('home-snap-is-animating');
        };

        const travelToSnap = (targetIndex) => {
            if (!snapIsEnabled() || !snapStops.length || snapIsAnimating) return;
            const boundedIndex = Math.max(0, Math.min(snapStops.length - 1, targetIndex));
            const targetPosition = snapStops[boundedIndex];
            const startPosition = window.scrollY;
            const distance = targetPosition - startPosition;
            if (Math.abs(distance) < 2) return;

            const indexDistance = Math.abs(boundedIndex - nearestSnapIndex());
            const duration = indexDistance <= 1
                ? SNAP_TRAVEL_DURATION
                : Math.min(SNAP_LONG_TRAVEL_MAX, SNAP_TRAVEL_DURATION + ((indexDistance - 1) * 75));
            const startTime = performance.now();
            if (updateFrame) window.cancelAnimationFrame(updateFrame);
            updateFrame = null;
            snapIsAnimating = true;
            root.classList.add('home-snap-is-animating');

            const advance = (time) => {
                const progress = clamp((time - startTime) / duration);
                window.scrollTo(0, startPosition + (distance * easeInOutSine(progress)));
                update();
                if (progress < 1 && snapIsEnabled()) {
                    snapAnimationFrame = window.requestAnimationFrame(advance);
                    return;
                }

                window.scrollTo(0, targetPosition);
                snapAnimationFrame = null;
                snapIsAnimating = false;
                snapCooldownUntil = performance.now() + SNAP_MOMENTUM_COOLDOWN;
                root.classList.remove('home-snap-is-animating');
                scheduleUpdate();
            };

            snapAnimationFrame = window.requestAnimationFrame(advance);
        };

        const travelByDirection = (direction) => {
            if (!snapStops.length) measure();
            const currentIndex = nearestSnapIndex();
            travelToSnap(currentIndex + direction);
        };

        const onWheel = (event) => {
            if (!snapIsEnabled()) return;
            const lastStop = snapStops.at(-1);
            const isPastFinalScene = Number.isFinite(lastStop) && window.scrollY > lastStop + 2;
            const isLeavingFinalScene = Number.isFinite(lastStop)
                && window.scrollY >= lastStop - 2
                && event.deltaY > 0;
            if (isPastFinalScene && event.deltaY < 0) {
                event.preventDefault();
                root.classList.add('home-footer-scroll');
                travelToSnap(snapStops.length - 1);
                return;
            }
            if (isPastFinalScene || isLeavingFinalScene) {
                wheelDelta = 0;
                root.classList.add('home-footer-scroll');
                return;
            }
            event.preventDefault();
            if (snapIsAnimating || performance.now() < snapCooldownUntil) return;

            wheelDelta += event.deltaY;
            if (wheelResetTimer) window.clearTimeout(wheelResetTimer);
            wheelResetTimer = window.setTimeout(() => {
                wheelDelta = 0;
                wheelResetTimer = null;
            }, 140);
            if (Math.abs(wheelDelta) < SNAP_WHEEL_THRESHOLD) return;

            const direction = wheelDelta > 0 ? 1 : -1;
            wheelDelta = 0;
            travelByDirection(direction);
        };

        const onKeydown = (event) => {
            if (!snapIsEnabled() || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
            const target = event.target;
            if (target instanceof Element && target.closest('a, button, input, select, textarea, [contenteditable="true"]')) return;

            const currentIndex = nearestSnapIndex();
            const isForwardKey = event.key === 'ArrowDown'
                || event.key === 'PageDown'
                || (event.key === ' ' && !event.shiftKey);
            const isBackwardKey = event.key === 'ArrowUp'
                || event.key === 'PageUp'
                || (event.key === ' ' && event.shiftKey);
            const isAtFinalScene = currentIndex === snapStops.length - 1
                && window.scrollY >= snapStops.at(-1) - 2;
            if (isBackwardKey && window.scrollY > snapStops.at(-1) + 2) {
                event.preventDefault();
                root.classList.add('home-footer-scroll');
                travelToSnap(snapStops.length - 1);
                return;
            }
            if (event.key === 'End' || (isForwardKey && isAtFinalScene)) {
                event.preventDefault();
                enterFooter();
                return;
            }

            let targetIndex = null;
            if (event.key === 'ArrowDown' || event.key === 'PageDown' || (event.key === ' ' && !event.shiftKey)) {
                targetIndex = nearestSnapIndex() + 1;
            } else if (event.key === 'ArrowUp' || event.key === 'PageUp' || (event.key === ' ' && event.shiftKey)) {
                targetIndex = nearestSnapIndex() - 1;
            } else if (event.key === 'Home') {
                targetIndex = 0;
            }
            if (targetIndex === null) return;

            event.preventDefault();
            travelToSnap(targetIndex);
        };

        const onSceneLinkClick = (event) => {
            if (!snapIsEnabled()) return;
            const link = event.currentTarget;
            const target = document.querySelector(link.hash);
            const targetIndex = scenes.indexOf(target);
            if (targetIndex < 0) return;
            event.preventDefault();
            window.history.pushState(null, '', link.hash);
            travelToSnap(targetIndex);
        };

        const resetParallax = () => {
            parallaxStyleKey = '';
            stage.classList.remove('is-parallax-active', 'is-parallax-ready');
            stage.style.removeProperty('--hero-background-scale');
            stage.style.removeProperty('--hero-background-y');
            stage.style.removeProperty('--hero-backdrop-y');
            stage.style.removeProperty('--hero-copy-opacity');
            stage.style.removeProperty('--hero-copy-y');
            stage.style.removeProperty('--hero-signature-opacity');
        };

        const renderParallax = () => {
            if (reducedMotion.matches) {
                resetParallax();
                return;
            }
            if (!parallaxGeometry) measure();
            const progress = clamp((window.scrollY - parallaxGeometry.start) / (parallaxGeometry.end - parallaxGeometry.start));
            const depthProgress = smoothstep(0.02, 0.96, progress);
            const copyFade = smoothstep(0.22, 0.72, progress);
            const signatureFade = smoothstep(0.5, 0.78, progress);
            const backgroundTravel = mobileLayout.matches ? 19 : 42;
            const backgroundScale = mobileLayout.matches ? 1.12 : 1.14;
            const backdropTravel = mobileLayout.matches ? 6 : 12;
            const backgroundY = `${format(backgroundTravel * depthProgress)}px`;
            const currentBackgroundScale = String(format(backgroundScale + (0.006 * depthProgress)));
            const backdropY = `${format(backdropTravel * depthProgress)}px`;
            const copyOpacity = String(format(1 - copyFade));
            const copyY = `${format(-12 * copyFade)}px`;
            const signatureOpacity = String(format(1 - signatureFade));
            const isActive = progress > 0 && progress < 1;
            const nextStyleKey = [backgroundY, currentBackgroundScale, backdropY, copyOpacity, copyY, signatureOpacity, isActive].join(':');
            if (nextStyleKey === parallaxStyleKey) return;

            stage.style.setProperty('--hero-background-y', backgroundY);
            stage.style.setProperty('--hero-background-scale', currentBackgroundScale);
            stage.style.setProperty('--hero-backdrop-y', backdropY);
            stage.style.setProperty('--hero-copy-opacity', copyOpacity);
            stage.style.setProperty('--hero-copy-y', copyY);
            stage.style.setProperty('--hero-signature-opacity', signatureOpacity);
            stage.classList.toggle('is-parallax-active', isActive);
            parallaxStyleKey = nextStyleKey;
        };

        const update = () => {
            setActiveScene();
            setFooterVisibility();
            renderParallax();
            renderHandoff();
            renderDepth();
            updateFrame = null;
        };

        const scheduleUpdate = () => {
            if (snapIsAnimating) return;
            if (!updateFrame) updateFrame = window.requestAnimationFrame(update);
        };

        const scheduleMeasure = () => {
            if (resizeFrame) window.cancelAnimationFrame(resizeFrame);
            resizeFrame = window.requestAnimationFrame(() => {
                parallaxGeometry = null;
                measure();
                update();
                resizeFrame = null;
            });
        };

        const configureMotion = () => {
            const snapEnabled = snapIsEnabled();
            root.classList.toggle('home-scroll-snap', snapEnabled);
            root.classList.toggle('home-depth-ready', snapEnabled);
            if (!snapEnabled) cancelSnapTravel();
            if (reducedMotion.matches) {
                scenes.forEach((scene) => scene.classList.add('is-scene-seen'));
                resetParallax();
                resetDepth();
                hideHandoff();
            } else if (background.complete && background.naturalWidth) {
                stage.classList.add('is-parallax-ready');
            }
            scheduleMeasure();
        };

        const revealObserver = 'IntersectionObserver' in window
            ? new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-scene-seen');
                        revealObserver.unobserve(entry.target);
                    }
                });
            }, { rootMargin: '0px 0px -10% 0px', threshold: 0.12 })
            : null;

        setActiveScene();
        handoffAnchors.forEach((anchor) => {
            const image = anchor.closest('.home-hero-media, .home-feature-media')?.querySelector('.home-hero-photo-fallback, img');
            image?.addEventListener('load', scheduleMeasure, { once: true });
        });
        scenes.forEach((scene) => {
            if (revealObserver) revealObserver.observe(scene);
            else scene.classList.add('is-scene-seen');
        });
        root.classList.add('home-scroll-story-ready');

        window.addEventListener('scroll', scheduleUpdate, { passive: true });
        window.addEventListener('wheel', onWheel, { passive: false });
        window.addEventListener('keydown', onKeydown);
        window.addEventListener('resize', scheduleMeasure);
        window.addEventListener('load', scheduleMeasure, { once: true });
        reducedMotion.addEventListener('change', configureMotion);
        mobileLayout.addEventListener('change', scheduleMeasure);
        snapLayout.addEventListener('change', configureMotion);
        sceneLinks.forEach((link) => link.addEventListener('click', onSceneLinkClick));
        configureMotion();
    });
})();
